"""Model-level scheduling and logging for TENGBench evaluation."""

from __future__ import annotations

import concurrent.futures
import logging
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Any

import yaml

from src.worker import FatalRequestError, QuestionResult, evaluate_question


WORKERS = 32
MAX_RETRIES = 20
REQUEST_TIMEOUT_SECONDS = 120.0
RETRY_BASE_SECONDS = 1.0
RETRY_MAX_SECONDS = 60.0

TEST_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = TEST_DIR.parents[1]
QUESTION_ROOT = PROJECT_DIR / "benchmark" / "question"
RESULT_ROOT = PROJECT_DIR / "result"
MODELS_PATH = TEST_DIR / "models.yaml"


def load_models() -> dict[str, dict[str, str]]:
    with MODELS_PATH.open("r", encoding="utf-8") as handle:
        models = yaml.safe_load(handle) or {}

    if not isinstance(models, dict):
        raise ValueError(f"{MODELS_PATH} must contain a top-level mapping.")

    required = {"base_url", "model", "enable_thinking"}
    for config_name, config in models.items():
        if not isinstance(config, dict) or required - config.keys():
            missing = ", ".join(sorted(required - set(config or {})))
            raise ValueError(f"Invalid configuration for {config_name!r}; missing: {missing}")
        if "api_key" not in config and "api_key_env" not in config:
            raise ValueError(
                f"Invalid configuration for {config_name!r}; provide api_key or api_key_env."
            )
        if not isinstance(config["enable_thinking"], bool):
            raise ValueError(
                f"Invalid configuration for {config_name!r}; enable_thinking must be true or false."
            )
    return models


def configure_logger(model_dir: Path) -> logging.Logger:
    started_at = datetime.now().strftime("%y-%m-%d_%H-%M-%S")
    log_path = model_dir / f"{started_at}.log"
    logger = logging.getLogger(f"tengbench.{started_at}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        "[%(levelname)s] %(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def checkpoint_state(output_path: Path) -> str:
    """Return the resumable state recorded for one question result."""
    if not output_path.is_file():
        return "missing"
    try:
        import json

        with output_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
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
    except (OSError, ValueError, TypeError):
        return "missing"


def run(*, model_name: str, judge_name: str | None) -> None:
    models = load_models()
    if model_name not in models:
        raise SystemExit(f"Unknown --model {model_name!r}. Add it to {MODELS_PATH}.")
    if not QUESTION_ROOT.is_dir():
        raise SystemExit(f"Question directory does not exist: {QUESTION_ROOT}")

    all_question_paths = sorted(QUESTION_ROOT.rglob("*.json"))
    # DG3 is deliberately excluded from the benchmark evaluation protocol.
    question_paths = [
        path
        for path in all_question_paths
        if path.relative_to(QUESTION_ROOT).parts[:2] != ("L3", "DG3")
    ]
    excluded_count = len(all_question_paths) - len(question_paths)
    has_l3_questions = any(path.relative_to(QUESTION_ROOT).parts[0] == "L3" for path in question_paths)
    if has_l3_questions and judge_name is None:
        raise SystemExit("--judge is required because the question set contains L3 questions.")
    if judge_name is not None and judge_name not in models:
        raise SystemExit(f"Unknown --judge {judge_name!r}. Add it to {MODELS_PATH}.")

    model_dir = RESULT_ROOT / model_name
    model_dir.mkdir(parents=True, exist_ok=True)
    logger = configure_logger(model_dir)
    stop_event = Event()
    completed_paths: list[Path] = []
    judge_resume_paths: list[Path] = []
    new_paths: list[Path] = []
    for path in question_paths:
        state = checkpoint_state(model_dir / path.relative_to(QUESTION_ROOT))
        if state == "completed":
            completed_paths.append(path)
        elif state == "model_saved":
            judge_resume_paths.append(path)
        else:
            new_paths.append(path)
    # Finish preserved tested-model answers first; these tasks only need the
    # expert request and never repeat the tested-model API call.
    pending_paths = judge_resume_paths + new_paths
    logger.info(
        "run_started | mode=resume | model=%s | judge=%s | total=%d | excluded=%d | "
        "completed_skipped=%d | judge_resume=%d | fresh=%d | workers=%d",
        model_name,
        judge_name,
        len(question_paths),
        excluded_count,
        len(completed_paths),
        len(judge_resume_paths),
        len(new_paths),
        WORKERS,
    )

    completed = 0
    parse_errors = 0
    aborted_error: FatalRequestError | None = None
    future_to_path: dict[concurrent.futures.Future[QuestionResult], Path] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
        path_iter = iter(pending_paths)

        def submit_next() -> bool:
            if stop_event.is_set():
                return False
            try:
                question_path = next(path_iter)
            except StopIteration:
                return False
            future = executor.submit(
                evaluate_question,
                question_path=question_path,
                question_root=QUESTION_ROOT,
                model_dir=model_dir,
                tested_config_name=model_name,
                tested_config=models[model_name],
                judge_config_name=judge_name,
                judge_config=models[judge_name] if judge_name is not None else None,
                stop_event=stop_event,
                max_retries=MAX_RETRIES,
                timeout_seconds=REQUEST_TIMEOUT_SECONDS,
                retry_base_seconds=RETRY_BASE_SECONDS,
                retry_max_seconds=RETRY_MAX_SECONDS,
                logger=logger,
            )
            future_to_path[future] = question_path
            return True

        for _ in range(min(WORKERS, len(pending_paths))):
            submit_next()

        while future_to_path:
            done, _ = concurrent.futures.wait(
                future_to_path, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for future in done:
                question_path = future_to_path.pop(future)
                try:
                    result = future.result()
                    completed += 1
                    parse_errors += result.answer_parse_error
                    logger.info(
                        "question_finished | qa_id=%s | model_attempts=%d | judge_attempts=%d | "
                        "answer_status=%s | elapsed_seconds=%.2f",
                        result.qa_id,
                        result.model_attempts,
                        result.judge_attempts,
                        result.answer_status,
                        result.elapsed_seconds,
                    )
                except FatalRequestError as error:
                    if aborted_error is None:
                        aborted_error = error
                        stop_event.set()
                        logger.error(
                            "model_aborted | qa_id=%s | phase=%s | failed_after=%d_attempts | error=%s",
                            error.qa_id,
                            error.phase,
                            MAX_RETRIES,
                            error,
                        )
                except Exception:
                    stop_event.set()
                    logger.exception("unexpected_worker_error | path=%s", question_path)
                    raise
                if not stop_event.is_set():
                    submit_next()

    if aborted_error:
        logger.error("run_finished | status=aborted | completed=%d | parse_errors=%d", completed, parse_errors)
        raise SystemExit(1)
    logger.info("run_finished | status=success | completed=%d | parse_errors=%d", completed, parse_errors)
