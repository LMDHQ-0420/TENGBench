"""Single-question worker: API calls, retries, parsing, judging, and result writing."""

from __future__ import annotations

import json
import logging
import os
import random
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError


ANSWER_PROMPT = """Answer the question below. Put the final answer, and only the final answer, in this format:

'''answer
your answer
'''"""

MULTIPLE_CHOICE_SUFFIX = """
This is a multiple-choice question. Between the delimiters, return exactly one option label
(for example: A). Do not include an explanation."""

JUDGE_PROMPT = """Evaluate the candidate answer using the question, reference answer, and rubric.
Return JSON only, without a Markdown fence or surrounding text. The top-level object must have
exactly these keys: score, per_rubric, reasoning. Evaluate every rubric item in its original order.
per_rubric must contain exactly one object per rubric item, with exactly these keys: key, score,
reasoning. Copy each rubric key exactly. Every item score and the total score must be numeric and
between 0 and 1. Compute the total score from the rubric weights and item scores. If the candidate
answer is absent because parsing failed, assign zero to every item and explain that cause."""

ANSWER_PATTERN = re.compile(r"'''answer\s*\n?(.*?)'''", re.IGNORECASE | re.DOTALL)


class FatalRequestError(RuntimeError):
    def __init__(self, qa_id: str, phase: str, cause: BaseException):
        super().__init__(str(cause))
        self.qa_id = qa_id
        self.phase = phase


@dataclass(frozen=True)
class QuestionResult:
    qa_id: str
    model_attempts: int
    judge_attempts: int
    answer_status: str
    answer_parse_error: int
    elapsed_seconds: float


def _timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _client(config: dict[str, str]) -> OpenAI:
    # api_key is a literal private key. api_key_env keeps compatibility with
    # configurations that store the name of an environment variable instead.
    if "api_key" in config:
        api_key = config["api_key"]
    else:
        api_key_env = config["api_key_env"]
        api_key = os.environ.get(api_key_env, api_key_env)
    if not api_key:
        raise ValueError("No API key is configured.")
    base_url = config["base_url"].rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    return OpenAI(base_url=base_url, api_key=api_key, max_retries=0)


def _is_retryable(error: BaseException) -> bool:
    if isinstance(error, (APIConnectionError, APITimeoutError, RateLimitError)):
        return True
    return isinstance(error, APIStatusError) and error.status_code in {408, 409, 429, 500, 502, 503, 504}


def _request(
    *,
    client: OpenAI,
    model: str,
    enable_thinking: bool,
    messages: list[dict[str, str]],
    qa_id: str,
    phase: str,
    stop_event: Event,
    max_retries: int,
    timeout_seconds: float,
    retry_base_seconds: float,
    retry_max_seconds: float,
    logger: logging.Logger,
) -> tuple[str, int]:
    last_error: BaseException | None = None
    for attempt in range(1, max_retries + 1):
        if stop_event.is_set():
            raise FatalRequestError(qa_id, phase, RuntimeError("run stopped"))
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                timeout=timeout_seconds,
                extra_body={"enable_thinking": enable_thinking},
            )
            # Some OpenAI-compatible gateways return the generated text
            # directly instead of the standard ChatCompletion object.
            if isinstance(response, str):
                content = response
            else:
                content = response.choices[0].message.content
            if content is None:
                raise ValueError("Model returned an empty message content.")
            if content.lstrip().lower().startswith(("<!doctype html", "<html")):
                raise ValueError("Gateway returned HTML instead of a model response.")
            return content, attempt
        except Exception as error:
            last_error = error
            if not _is_retryable(error) or attempt == max_retries:
                raise FatalRequestError(qa_id, phase, error) from error
            delay = min(retry_max_seconds, retry_base_seconds * (2 ** (attempt - 1)))
            delay += random.uniform(0, min(1.0, delay * 0.1))
            logger.warning(
                "request_retry | qa_id=%s | phase=%s | attempt=%d/%d | wait_seconds=%.2f | error=%s",
                qa_id,
                phase,
                attempt,
                max_retries,
                delay,
                error,
            )
            if stop_event.wait(delay):
                raise FatalRequestError(qa_id, phase, RuntimeError("run stopped")) from error
    raise FatalRequestError(qa_id, phase, last_error or RuntimeError("unknown request failure"))


def _extract_answer(raw_response: str) -> str | None:
    matches = ANSWER_PATTERN.findall(raw_response)
    if not matches:
        return None
    answer = matches[-1].strip()
    return answer or None


def _is_exact_match(candidate: str | None, expected: Any) -> bool:
    """L1/L2 answers are option labels; normalize whitespace and case only."""
    if candidate is None or expected is None:
        return False
    return candidate.strip().upper() == str(expected).strip().upper()


def _parse_judge_result(raw_response: str) -> dict[str, Any] | None:
    candidate = raw_response.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _write_json_atomically(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary_path = Path(handle.name)
    temporary_path.replace(path)


def evaluate_question(
    *,
    question_path: Path,
    question_root: Path,
    model_dir: Path,
    tested_config_name: str,
    tested_config: dict[str, str],
    judge_config_name: str | None,
    judge_config: dict[str, str] | None,
    stop_event: Event,
    max_retries: int,
    timeout_seconds: float,
    retry_base_seconds: float,
    retry_max_seconds: float,
    logger: logging.Logger,
) -> QuestionResult:
    started_monotonic = time.monotonic()
    with question_path.open("r", encoding="utf-8") as handle:
        question_data: dict[str, Any] = json.load(handle)
    qa_id = str(question_data["qa_id"])
    output_path = model_dir / question_path.relative_to(question_root)

    is_objective_question = question_data["layer"] in {"L1", "L2"}
    existing_result: dict[str, Any] | None = None
    existing_response: dict[str, Any] | None = None
    if output_path.is_file():
        try:
            with output_path.open("r", encoding="utf-8") as handle:
                existing_result = json.load(handle)
            candidate = existing_result.get("model_response")
            if candidate and candidate.get("status") in {"success", "answer_parse_error"}:
                existing_response = candidate
        except (OSError, ValueError, TypeError):
            existing_result = None

    if existing_response is not None:
        # The tested model has already answered. Resume directly from judging.
        tested_raw = existing_response["raw_response"]
        answer = existing_response.get("answer")
        answer_status = existing_response["status"]
        model_attempts = int(existing_response.get("attempts", 1))
        # Normalize legacy checkpoints as they are resumed, even if they were
        # created before the one-time result migration.
        model_response = dict(existing_response)
        model_response.pop("config_name", None)
        model_response["model"] = tested_config_name
    else:
        answer_prompt = ANSWER_PROMPT + (MULTIPLE_CHOICE_SUFFIX if is_objective_question else "")
        question_content = question_data["question"]
        if is_objective_question:
            options = question_data.get("options")
            if not isinstance(options, dict) or not options:
                raise ValueError(f"Objective question {qa_id} has no options mapping.")
            formatted_options = "\n".join(
                f"{label}. {text}" for label, text in sorted(options.items())
            )
            question_content = f"{question_content}\n\nOptions:\n{formatted_options}"
        tested_raw, model_attempts = _request(
            client=_client(tested_config),
            model=tested_config["model"],
            enable_thinking=tested_config["enable_thinking"],
            messages=[
                {"role": "system", "content": answer_prompt},
                {"role": "user", "content": question_content},
            ],
            qa_id=qa_id,
            phase="tested_model",
            stop_event=stop_event,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            retry_base_seconds=retry_base_seconds,
            retry_max_seconds=retry_max_seconds,
            logger=logger,
        )
        answer = _extract_answer(tested_raw)
        answer_status = "success" if answer is not None else "answer_parse_error"
        model_response = {
            # The persisted model value is the models.yaml configuration name,
            # which is also the result directory name.  The provider-facing
            # model ID remains an internal API-call detail.
            "model": tested_config_name,
            "raw_response": tested_raw,
            "answer": answer,
            "status": answer_status,
            "attempts": model_attempts,
            "finished_at": _timestamp(),
            "elapsed_seconds": round(time.monotonic() - started_monotonic, 3),
        }

    if is_objective_question:
        expected_answer = question_data["answer"]
        judge_attempts = 0
        evaluation = {
            "method": "exact_match",
            "expected_answer": expected_answer,
            "is_correct": _is_exact_match(answer, expected_answer),
            "status": "success",
        }
    else:
        if judge_config_name is None or judge_config is None:
            raise ValueError("An L3 question requires a configured judge model.")
        result_data = dict(question_data)
        result_data["model_response"] = model_response
        # Write before the expert request so a completed tested-model answer is
        # never lost to judge timeout, retry exhaustion, or process interruption.
        result_data["evaluation"] = {
            "method": "expert_rubric_judge",
            # As with model_response.model, persist the configuration name,
            # not the provider-facing model ID.
            "judge_model": judge_config_name,
            "status": "pending",
            "attempts": 0,
        }
        _write_json_atomically(output_path, result_data)
        judge_payload = {
            "question": question_data["question"],
            "reference_answer": question_data["reference_answer"],
            "rubric": question_data["rubric"],
            "candidate_answer": answer,
            "candidate_answer_status": answer_status,
        }
        judge_raw, judge_attempts = _request(
            client=_client(judge_config),
            model=judge_config["model"],
            enable_thinking=judge_config["enable_thinking"],
            messages=[
                {"role": "system", "content": JUDGE_PROMPT},
                {"role": "user", "content": json.dumps(judge_payload, ensure_ascii=False)},
            ],
            qa_id=qa_id,
            phase="judge_model",
            stop_event=stop_event,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            retry_base_seconds=retry_base_seconds,
            retry_max_seconds=retry_max_seconds,
            logger=logger,
        )
        judge_result = _parse_judge_result(judge_raw)
        evaluation = {
            "method": "expert_rubric_judge",
            "judge_model": judge_config_name,
            "raw_response": judge_raw,
            "result": judge_result,
            "status": "success" if judge_result is not None else "response_parse_error",
            "attempts": judge_attempts,
            "finished_at": _timestamp(),
        }
    elapsed_seconds = time.monotonic() - started_monotonic

    result_data = dict(question_data)
    result_data["model_response"] = model_response
    result_data["evaluation"] = evaluation
    _write_json_atomically(output_path, result_data)

    return QuestionResult(
        qa_id=qa_id,
        model_attempts=model_attempts,
        judge_attempts=judge_attempts,
        answer_status=answer_status,
        answer_parse_error=int(answer_status == "answer_parse_error"),
        elapsed_seconds=elapsed_seconds,
    )
