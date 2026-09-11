"""Offline contract tests for persisted TENGBench evaluation results."""

from __future__ import annotations

import json
import logging
import sys
import tempfile
import types
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch


TEST_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TEST_DIR))

# The contract test patches every API call, so it only needs import-compatible
# placeholders when the optional OpenAI SDK is absent from the test runtime.
try:
    import openai as _openai  # noqa: F401
except ModuleNotFoundError:
    openai_stub = types.ModuleType("openai")

    class _OpenAIError(Exception):
        pass

    class _OpenAI:
        pass

    openai_stub.APIConnectionError = _OpenAIError
    openai_stub.APIStatusError = _OpenAIError
    openai_stub.APITimeoutError = _OpenAIError
    openai_stub.OpenAI = _OpenAI
    openai_stub.RateLimitError = _OpenAIError
    sys.modules["openai"] = openai_stub

from src import worker  # noqa: E402


class ResultContractTest(unittest.TestCase):
    def _evaluate(
        self,
        question_data: dict[str, object],
        *,
        existing_model_response: dict[str, object] | None = None,
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            question_root = root / "question"
            question_path = question_root / question_data["layer"] / question_data["type"] / "q.json"  # type: ignore[operator]
            question_path.parent.mkdir(parents=True)
            question_path.write_text(
                json.dumps(question_data, ensure_ascii=False), encoding="utf-8"
            )
            model_dir = root / "result" / "tested-label"
            output_path = model_dir / question_path.relative_to(question_root)
            if existing_model_response is not None:
                output_path.parent.mkdir(parents=True)
                output_path.write_text(
                    json.dumps(
                        {
                            **question_data,
                            "model_response": existing_model_response,
                            "evaluation": {
                                "method": "expert_rubric_judge",
                                "status": "pending",
                                "attempts": 0,
                            },
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

            def fake_request(**kwargs: object) -> tuple[str, int]:
                if kwargs["phase"] == "judge_model":
                    return (
                        '{"score": 1.0, "per_rubric": [], "reasoning": "ok"}',
                        1,
                    )
                answer = "A" if question_data["layer"] == "L1" else "candidate"
                return f"'''answer\n{answer}\n'''", 1

            with patch.object(worker, "_client", return_value=object()), patch.object(
                worker, "_request", side_effect=fake_request
            ):
                worker.evaluate_question(
                    question_path=question_path,
                    question_root=question_root,
                    model_dir=model_dir,
                    tested_config_name="tested-label",
                    tested_config={
                        "model": "provider-model-id",
                        "base_url": "https://invalid.example",
                        "api_key": "unused",
                        "enable_thinking": False,
                    },
                    judge_config_name="judge-label",
                    judge_config={
                        "model": "provider-judge-id",
                        "base_url": "https://invalid.example",
                        "api_key": "unused",
                        "enable_thinking": False,
                    },
                    stop_event=Event(),
                    max_retries=1,
                    timeout_seconds=1,
                    retry_base_seconds=0,
                    retry_max_seconds=0,
                    logger=logging.getLogger("test-result-contract"),
                )

            return json.loads(output_path.read_text(encoding="utf-8"))

    def test_objective_result_uses_directory_model_label(self) -> None:
        result = self._evaluate(
            {
                "qa_id": "L1_test",
                "type": "BK1",
                "layer": "L1",
                "question": "Pick A.",
                "options": {"A": "correct", "B": "wrong"},
                "answer": "A",
            }
        )

        self.assertEqual(result["model_response"]["model"], "tested-label")
        self.assertNotIn("config_name", result["model_response"])
        self.assertEqual(result["evaluation"]["method"], "exact_match")
        self.assertTrue(result["evaluation"]["is_correct"])

    def test_expert_result_uses_judge_configuration_label(self) -> None:
        result = self._evaluate(
            {
                "qa_id": "L3_test",
                "type": "DG1",
                "layer": "L3",
                "question": "Explain.",
                "reference_answer": "Reference.",
                "rubric": [],
            }
        )

        self.assertEqual(result["model_response"]["model"], "tested-label")
        self.assertNotIn("config_name", result["model_response"])
        self.assertEqual(result["evaluation"]["judge_model"], "judge-label")
        self.assertNotIn("judge_config_name", result["evaluation"])
        self.assertEqual(result["evaluation"]["result"]["score"], 1.0)

    def test_legacy_pending_result_is_normalized_when_resumed(self) -> None:
        result = self._evaluate(
            {
                "qa_id": "L3_resume_test",
                "type": "DG1",
                "layer": "L3",
                "question": "Explain.",
                "reference_answer": "Reference.",
                "rubric": [],
            },
            existing_model_response={
                "config_name": "tested-label",
                "model": "provider-model-id",
                "raw_response": "'''answer\ncandidate\n'''",
                "answer": "candidate",
                "status": "success",
                "attempts": 1,
                "finished_at": "2026-09-02T00:00:00+08:00",
                "elapsed_seconds": 1.0,
            },
        )

        self.assertEqual(result["model_response"]["model"], "tested-label")
        self.assertNotIn("config_name", result["model_response"])


if __name__ == "__main__":
    unittest.main()
