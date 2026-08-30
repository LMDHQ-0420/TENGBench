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

JUDGE_PROMPT = """Evaluate the candidate answer using the question, reference answer, and rubric.
Return JSON only with exactly these keys: score, per_rubric, reasoning.
score must be a number between 0 and 1. per_rubric must be a list."""

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
    api_key = os.environ.get(config["api_key_env"])
    if not api_key:
        raise ValueError(f"Environment variable {config['api_key_env']!r} is not set.")
    return OpenAI(base_url=config["base_url"], api_key=api_key, max_retries=0)


def _is_retryable(error: BaseException) -> bool:
    if isinstance(error, (APIConnectionError, APITimeoutError, RateLimitError)):
        return True
    return isinstance(error, APIStatusError) and error.status_code in {408, 409, 429, 500, 502, 503, 504}


def _request(
    *,
    client: OpenAI,
    model: str,
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
            )
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Model returned an empty message content.")
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
    judge_config_name: str,
    judge_config: dict[str, str],
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

    tested_raw, model_attempts = _request(
        client=_client(tested_config),
        model=tested_config["model"],
        messages=[
            {"role": "system", "content": ANSWER_PROMPT},
            {"role": "user", "content": question_data["question"]},
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
    elapsed_seconds = time.monotonic() - started_monotonic

    result_data = dict(question_data)
    result_data["model_response"] = {
        "config_name": tested_config_name,
        "model": tested_config["model"],
        "raw_response": tested_raw,
        "answer": answer,
        "status": answer_status,
        "attempts": model_attempts,
        "finished_at": _timestamp(),
    }
    result_data["evaluation"] = {
        "judge_config_name": judge_config_name,
        "judge_model": judge_config["model"],
        "raw_response": judge_raw,
        "result": judge_result,
        "status": "success" if judge_result is not None else "response_parse_error",
        "attempts": judge_attempts,
        "finished_at": _timestamp(),
    }
    result_data["model_response"]["elapsed_seconds"] = round(elapsed_seconds, 3)
    _write_json_atomically(model_dir / question_path.relative_to(question_root), result_data)

    return QuestionResult(
        qa_id=qa_id,
        model_attempts=model_attempts,
        judge_attempts=judge_attempts,
        answer_status=answer_status,
        answer_parse_error=int(answer_status == "answer_parse_error"),
        elapsed_seconds=elapsed_seconds,
    )
