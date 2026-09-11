"""Validate subagent responses and atomically write TENGBench result batches."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from read_task import (
    MAX_BATCH_SIZE,
    QUESTION_ROOT,
    RESULT_ROOT,
    checkpoint_state,
    is_excluded,
    load_json_object,
    parse_model_name,
    resolve_question_path,
    result_path_for,
    timestamp,
    validate_model_name,
)


ANSWER_PATTERN = re.compile(r"'''answer\s*\n?(.*?)'''", re.IGNORECASE | re.DOTALL)
SKILL_JUDGE_MODEL = "current-dialogue-model"


def extract_answer(raw_response: str) -> str | None:
    matches = ANSWER_PATTERN.findall(raw_response)
    if not matches:
        return None
    answer = matches[-1].strip()
    return answer or None


def is_exact_match(candidate: str | None, expected: Any) -> bool:
    if candidate is None or expected is None:
        return False
    return candidate.strip().upper() == str(expected).strip().upper()


def parse_judge_result(raw_response: str) -> dict[str, Any] | None:
    """Match evaluation/api's judge-response parser exactly."""
    candidate = raw_response.strip()
    if candidate.startswith("```"):
        candidate = re.sub(
            r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE
        )
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def write_json_atomically(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary_path = Path(handle.name)
    temporary_path.replace(path)


def _read_stdin_payload() -> dict[str, Any]:
    # A single JSON line lets an orchestrator send a batch through an
    # interactive stdin session without creating an intermediate file.
    line = sys.stdin.readline()
    if not line:
        raise ValueError("Expected one JSON object on stdin")
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid stdin JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("stdin payload must be a JSON object")
    return payload


def _response_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    responses = payload.get("responses")
    if not isinstance(responses, list) or not responses:
        raise ValueError("stdin payload must contain a non-empty responses list")
    if len(responses) > MAX_BATCH_SIZE:
        raise ValueError(f"A batch may contain at most {MAX_BATCH_SIZE} responses")
    if not all(isinstance(item, dict) for item in responses):
        raise ValueError("Every response must be a JSON object")
    return responses


def _response_identity(item: dict[str, Any]) -> tuple[str, str, str, int]:
    qa_id = item.get("qa_id")
    question_path = item.get("question_path")
    raw_response = item.get("raw_response")
    attempts = item.get("attempts", 1)
    if not isinstance(qa_id, str) or not qa_id:
        raise ValueError("Every response requires a non-empty qa_id")
    if not isinstance(question_path, str) or not question_path:
        raise ValueError(f"Response {qa_id!r} requires question_path")
    if not isinstance(raw_response, str):
        raise ValueError(f"Response {qa_id!r} requires string raw_response")
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
        raise ValueError(f"Response {qa_id!r} attempts must be a positive integer")
    return qa_id, question_path, raw_response, attempts


def _elapsed_seconds(item: dict[str, Any]) -> float:
    issued_at = item.get("issued_at")
    if not isinstance(issued_at, str):
        raise ValueError("Every answer response requires issued_at from read_task.py")
    try:
        issued = datetime.fromisoformat(issued_at)
    except ValueError as error:
        raise ValueError(f"Invalid issued_at timestamp: {issued_at!r}") from error
    if issued.tzinfo is None:
        raise ValueError("issued_at must contain a timezone")
    elapsed = datetime.now(timezone.utc) - issued.astimezone(timezone.utc)
    return round(max(0.0, elapsed.total_seconds()), 3)


def _validated_question(
    *,
    qa_id: str,
    relative_path: str,
    question_root: Path,
) -> tuple[Path, dict[str, Any]]:
    question_path = resolve_question_path(relative_path, question_root)
    relative = question_path.relative_to(question_root.resolve())
    if is_excluded(relative):
        raise ValueError(f"DG3 is excluded from evaluation: {relative.as_posix()}")
    question_data = load_json_object(question_path)
    if str(question_data.get("qa_id")) != qa_id:
        raise ValueError(
            f"qa_id {qa_id!r} does not match question file {relative.as_posix()}"
        )
    return question_path, question_data


def _ensure_unique(items: list[dict[str, Any]]) -> None:
    identities: set[tuple[str, str]] = set()
    for item in items:
        qa_id, question_path, _, _ = _response_identity(item)
        identity = (qa_id, question_path)
        if identity in identities:
            raise ValueError(f"Duplicate response in batch: {qa_id}")
        identities.add(identity)


def write_answer_batch(
    *,
    model: str,
    payload: dict[str, Any],
    question_root: Path = QUESTION_ROOT,
    result_root: Path = RESULT_ROOT,
) -> dict[str, Any]:
    validate_model_name(model)
    items = _response_items(payload)
    _ensure_unique(items)
    planned: list[tuple[Path, dict[str, Any], str, str]] = []
    acknowledgements: list[dict[str, str]] = []

    # Build and validate the complete batch before writing its first result.
    for item in items:
        qa_id, relative_path, raw_response, attempts = _response_identity(item)
        question_path, question_data = _validated_question(
            qa_id=qa_id,
            relative_path=relative_path,
            question_root=question_root,
        )
        output_path = result_path_for(
            model=model,
            question_path=question_path,
            question_root=question_root,
            result_root=result_root,
        )
        state = checkpoint_state(output_path)
        if state in {"model_saved", "completed"}:
            acknowledgements.append(
                {"qa_id": qa_id, "action": "skipped", "state": state}
            )
            continue

        answer = extract_answer(raw_response)
        answer_status = "success" if answer is not None else "answer_parse_error"
        model_response = {
            "model": model,
            "raw_response": raw_response,
            "answer": answer,
            "status": answer_status,
            "attempts": attempts,
            "finished_at": timestamp(),
            "elapsed_seconds": _elapsed_seconds(item),
        }

        layer = question_data.get("layer")
        if layer in {"L1", "L2"}:
            evaluation = {
                "method": "exact_match",
                "expected_answer": question_data["answer"],
                "is_correct": is_exact_match(answer, question_data["answer"]),
                "status": "success",
            }
            resulting_state = "completed"
        elif layer == "L3":
            evaluation = {
                "method": "expert_rubric_judge",
                "judge_model": SKILL_JUDGE_MODEL,
                "status": "pending",
                "attempts": 0,
            }
            resulting_state = "model_saved"
        else:
            raise ValueError(f"Unsupported layer {layer!r}: {question_path}")

        result_data = dict(question_data)
        result_data["model_response"] = model_response
        result_data["evaluation"] = evaluation
        planned.append((output_path, result_data, qa_id, resulting_state))

    for output_path, result_data, qa_id, resulting_state in planned:
        write_json_atomically(output_path, result_data)
        acknowledgements.append(
            {"qa_id": qa_id, "action": "written", "state": resulting_state}
        )

    return {
        "status": "ok",
        "mode": "answer",
        "model": model,
        "received": len(items),
        "written": len(planned),
        "skipped": len(items) - len(planned),
        "items": acknowledgements,
    }


def write_judge_batch(
    *,
    model: str,
    payload: dict[str, Any],
    question_root: Path = QUESTION_ROOT,
    result_root: Path = RESULT_ROOT,
) -> dict[str, Any]:
    validate_model_name(model)
    items = _response_items(payload)
    _ensure_unique(items)
    planned: list[tuple[Path, dict[str, Any], str]] = []
    acknowledgements: list[dict[str, str]] = []

    for item in items:
        qa_id, relative_path, raw_response, attempts = _response_identity(item)
        question_path, question_data = _validated_question(
            qa_id=qa_id,
            relative_path=relative_path,
            question_root=question_root,
        )
        if question_data.get("layer") != "L3":
            raise ValueError(f"Only L3 questions use expert judging: {relative_path}")
        output_path = result_path_for(
            model=model,
            question_path=question_path,
            question_root=question_root,
            result_root=result_root,
        )
        state = checkpoint_state(output_path)
        if state == "completed":
            acknowledgements.append(
                {"qa_id": qa_id, "action": "skipped", "state": state}
            )
            continue
        if state != "model_saved":
            raise ValueError(f"Question has no saved model answer to judge: {qa_id}")

        existing_result = load_json_object(output_path)
        model_response = existing_result.get("model_response")
        if not isinstance(model_response, dict):
            raise ValueError(f"Missing model_response object: {output_path}")
        if "config_name" in model_response or model_response.get("model") != model:
            raise ValueError(f"model_response does not use the unified model label: {output_path}")

        judge_result = parse_judge_result(raw_response)
        evaluation = {
            "method": "expert_rubric_judge",
            "judge_model": SKILL_JUDGE_MODEL,
            "raw_response": raw_response,
            "result": judge_result,
            "status": "success" if judge_result is not None else "response_parse_error",
            "attempts": attempts,
            "finished_at": timestamp(),
        }
        result_data = dict(question_data)
        result_data["model_response"] = model_response
        result_data["evaluation"] = evaluation
        planned.append((output_path, result_data, qa_id))

    for output_path, result_data, qa_id in planned:
        write_json_atomically(output_path, result_data)
        acknowledgements.append(
            {"qa_id": qa_id, "action": "written", "state": "completed"}
        )

    return {
        "status": "ok",
        "mode": "judge",
        "model": model,
        "received": len(items),
        "written": len(planned),
        "skipped": len(items) - len(planned),
        "items": acknowledgements,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write TENGBench skill-evaluation results.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("answer", "judge"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--model", required=True, type=parse_model_name)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        payload = _read_stdin_payload()
        if args.command == "answer":
            result = write_answer_batch(model=args.model, payload=payload)
        else:
            result = write_judge_batch(model=args.model, payload=payload)
    except (KeyError, OSError, TypeError, ValueError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False))
        raise SystemExit(2) from error
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
