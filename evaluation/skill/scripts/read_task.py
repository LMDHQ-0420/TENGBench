"""Read TENGBench answer or judge tasks without exposing direct file access to skills."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Literal


MAX_BATCH_SIZE = 32
SCRIPT_DIR = Path(__file__).resolve().parent
TEST_SKILL_DIR = SCRIPT_DIR.parent
PROJECT_DIR = TEST_SKILL_DIR.parents[1]
QUESTION_ROOT = PROJECT_DIR / "benchmark" / "question"
RESULT_ROOT = PROJECT_DIR / "result"

CheckpointState = Literal["missing", "model_saved", "completed"]


def timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def validate_model_name(value: str) -> str:
    if (
        not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or Path(value).name != value
    ):
        raise ValueError("model must be one non-empty result-directory name")
    return value


def parse_model_name(value: str) -> str:
    try:
        return validate_model_name(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def parse_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("limit must be an integer") from error
    if not 1 <= limit <= MAX_BATCH_SIZE:
        raise argparse.ArgumentTypeError(
            f"limit must be between 1 and {MAX_BATCH_SIZE}"
        )
    return limit


def validate_relative_path(value: str) -> PurePosixPath:
    if not value or "\\" in value:
        raise ValueError("question_path must be a non-empty POSIX relative path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("question_path must stay below benchmark/question")
    if relative.suffix != ".json":
        raise ValueError("question_path must name a JSON file")
    return relative


def parse_cursor(value: str) -> str:
    try:
        return validate_relative_path(value).as_posix()
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read valid JSON from {path}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def resolve_question_path(relative_value: str, question_root: Path = QUESTION_ROOT) -> Path:
    relative = validate_relative_path(relative_value)
    root = question_root.resolve()
    path = (root / Path(*relative.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError("question_path escapes benchmark/question") from error
    if not path.is_file():
        raise ValueError(f"Question does not exist: {relative.as_posix()}")
    return path


def result_path_for(
    *,
    model: str,
    question_path: Path,
    question_root: Path = QUESTION_ROOT,
    result_root: Path = RESULT_ROOT,
) -> Path:
    validate_model_name(model)
    relative = question_path.resolve().relative_to(question_root.resolve())
    root = result_root.resolve()
    model_dir = (root / model).resolve()
    try:
        model_dir.relative_to(root)
    except ValueError as error:
        raise ValueError("model result directory escapes result root") from error
    return model_dir / relative


def checkpoint_state(output_path: Path) -> CheckpointState:
    """Return the same resumable state used by evaluation/api."""
    if not output_path.is_file():
        return "missing"
    try:
        data = load_json_object(output_path)
        model_saved = data.get("model_response", {}).get("status") in {
            "success",
            "answer_parse_error",
        }
        evaluation_finished = data.get("evaluation", {}).get("status") in {
            "success",
            "response_parse_error",
        }
        if model_saved and evaluation_finished:
            return "completed"
        if model_saved:
            return "model_saved"
        return "missing"
    except (ValueError, TypeError, AttributeError):
        return "missing"


def iter_question_paths(question_root: Path = QUESTION_ROOT) -> list[Path]:
    if not question_root.is_dir():
        raise ValueError(f"Question directory does not exist: {question_root}")
    return sorted(
        question_root.rglob("*.json"),
        key=lambda path: path.relative_to(question_root).as_posix(),
    )


def is_excluded(relative_path: Path | PurePosixPath) -> bool:
    return relative_path.parts[:2] == ("L3", "DG3")


def _qa_identity(question_data: dict[str, Any], path: Path) -> tuple[str, str, str]:
    try:
        qa_id = str(question_data["qa_id"])
        layer = str(question_data["layer"])
        question_type = str(question_data["type"])
    except KeyError as error:
        raise ValueError(f"Missing required question field {error.args[0]!r}: {path}") from error
    return qa_id, layer, question_type


def _answer_content(question_data: dict[str, Any], path: Path) -> tuple[str, bool]:
    try:
        content = str(question_data["question"])
        layer = str(question_data["layer"])
    except KeyError as error:
        raise ValueError(f"Missing required question field {error.args[0]!r}: {path}") from error
    is_objective = layer in {"L1", "L2"}
    if is_objective:
        options = question_data.get("options")
        if not isinstance(options, dict) or not options:
            raise ValueError(f"Objective question has no options mapping: {path}")
        formatted_options = "\n".join(
            f"{label}. {text}" for label, text in sorted(options.items())
        )
        content = f"{content}\n\nOptions:\n{formatted_options}"
    return content, is_objective


def _after_cursor(relative: str, cursor: str | None) -> bool:
    return cursor is None or relative > cursor


def read_answer_tasks(
    *,
    model: str,
    limit: int,
    after: str | None = None,
    question_root: Path = QUESTION_ROOT,
    result_root: Path = RESULT_ROOT,
) -> dict[str, Any]:
    validate_model_name(model)
    if not 1 <= limit <= MAX_BATCH_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_BATCH_SIZE}")
    if after is not None:
        after = validate_relative_path(after).as_posix()

    candidates: list[dict[str, Any]] = []
    for path in iter_question_paths(question_root):
        relative_path = path.relative_to(question_root)
        relative = relative_path.as_posix()
        if is_excluded(relative_path) or not _after_cursor(relative, after):
            continue
        output_path = result_path_for(
            model=model,
            question_path=path,
            question_root=question_root,
            result_root=result_root,
        )
        if checkpoint_state(output_path) != "missing":
            continue
        question_data = load_json_object(path)
        qa_id, layer, question_type = _qa_identity(question_data, path)
        content, is_objective = _answer_content(question_data, path)
        candidates.append(
            {
                "qa_id": qa_id,
                "question_path": relative,
                "layer": layer,
                "type": question_type,
                "is_objective": is_objective,
                "content": content,
                "issued_at": timestamp(),
            }
        )
        if len(candidates) > limit:
            break

    has_more = len(candidates) > limit
    tasks = candidates[:limit]
    return {
        "schema_version": 1,
        "mode": "answer",
        "model": model,
        "limit": limit,
        "tasks": tasks,
        "next_cursor": tasks[-1]["question_path"] if tasks else after,
        "has_more": has_more,
    }


def read_judge_tasks(
    *,
    model: str,
    limit: int,
    after: str | None = None,
    question_root: Path = QUESTION_ROOT,
    result_root: Path = RESULT_ROOT,
) -> dict[str, Any]:
    validate_model_name(model)
    if not 1 <= limit <= MAX_BATCH_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_BATCH_SIZE}")
    if after is not None:
        after = validate_relative_path(after).as_posix()

    candidates: list[dict[str, Any]] = []
    for path in iter_question_paths(question_root):
        relative_path = path.relative_to(question_root)
        relative = relative_path.as_posix()
        if is_excluded(relative_path) or not _after_cursor(relative, after):
            continue
        if relative_path.parts[:1] != ("L3",):
            continue
        output_path = result_path_for(
            model=model,
            question_path=path,
            question_root=question_root,
            result_root=result_root,
        )
        if checkpoint_state(output_path) != "model_saved":
            continue
        question_data = load_json_object(path)
        result_data = load_json_object(output_path)
        qa_id, layer, question_type = _qa_identity(question_data, path)
        model_response = result_data.get("model_response")
        if not isinstance(model_response, dict):
            raise ValueError(f"Missing model_response object: {output_path}")
        candidates.append(
            {
                "qa_id": qa_id,
                "question_path": relative,
                "layer": layer,
                "type": question_type,
                "payload": {
                    "question": question_data["question"],
                    "reference_answer": question_data["reference_answer"],
                    "rubric": question_data["rubric"],
                    "candidate_answer": model_response.get("answer"),
                    "candidate_answer_status": model_response.get("status"),
                },
                "issued_at": timestamp(),
            }
        )
        if len(candidates) > limit:
            break

    has_more = len(candidates) > limit
    tasks = candidates[:limit]
    return {
        "schema_version": 1,
        "mode": "judge",
        "model": model,
        "limit": limit,
        "tasks": tasks,
        "next_cursor": tasks[-1]["question_path"] if tasks else after,
        "has_more": has_more,
    }


def read_status(
    *,
    model: str,
    question_root: Path = QUESTION_ROOT,
    result_root: Path = RESULT_ROOT,
) -> dict[str, Any]:
    validate_model_name(model)
    counts = {
        "questions": 0,
        "excluded_dg3": 0,
        "awaiting_answer": 0,
        "awaiting_judge": 0,
        "completed": 0,
    }
    for path in iter_question_paths(question_root):
        relative_path = path.relative_to(question_root)
        if is_excluded(relative_path):
            counts["excluded_dg3"] += 1
            continue
        counts["questions"] += 1
        state = checkpoint_state(
            result_path_for(
                model=model,
                question_path=path,
                question_root=question_root,
                result_root=result_root,
            )
        )
        if state == "completed":
            counts["completed"] += 1
        elif state == "model_saved":
            counts["awaiting_judge"] += 1
        else:
            counts["awaiting_answer"] += 1
    return {"schema_version": 1, "mode": "status", "model": model, **counts}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read TENGBench skill-evaluation tasks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("answer", "judge"):
        task_parser = subparsers.add_parser(command)
        task_parser.add_argument("--model", required=True, type=parse_model_name)
        task_parser.add_argument("--limit", type=parse_limit, default=MAX_BATCH_SIZE)
        task_parser.add_argument("--after", type=parse_cursor)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--model", required=True, type=parse_model_name)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        if args.command == "answer":
            result = read_answer_tasks(
                model=args.model, limit=args.limit, after=args.after
            )
        elif args.command == "judge":
            result = read_judge_tasks(
                model=args.model, limit=args.limit, after=args.after
            )
        else:
            result = read_status(model=args.model)
    except (KeyError, OSError, TypeError, ValueError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False))
        raise SystemExit(2) from error
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
