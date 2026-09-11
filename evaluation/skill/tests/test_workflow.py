"""End-to-end tests for the skill-based TENGBench file workflow."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import read_task  # noqa: E402
import write_result  # noqa: E402


class SkillWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.question_root = self.root / "benchmark" / "question"
        self.result_root = self.root / "result"
        self.model = "tested-model-label"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _write_question(self, relative_path: str, data: dict[str, object]) -> Path:
        path = self.question_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return path

    def _read_result(self, relative_path: str) -> dict[str, object]:
        return read_task.load_json_object(self.result_root / self.model / relative_path)

    def test_objective_answer_is_isolated_and_api_compatible(self) -> None:
        relative_path = "L1/BK1/mechanism/q1.json"
        self._write_question(
            relative_path,
            {
                "qa_id": "L1_test_001",
                "type": "BK1",
                "layer": "L1",
                "question": "Choose the correct option.",
                "options": {"B": "wrong", "A": "correct"},
                "answer": "A",
                "source_excerpt": "hidden source",
            },
        )

        batch = read_task.read_answer_tasks(
            model=self.model,
            limit=1,
            question_root=self.question_root,
            result_root=self.result_root,
        )
        self.assertEqual(len(batch["tasks"]), 1)
        task = batch["tasks"][0]
        self.assertEqual(
            set(task),
            {
                "qa_id",
                "question_path",
                "layer",
                "type",
                "is_objective",
                "content",
                "issued_at",
            },
        )
        self.assertNotIn("hidden source", task["content"])
        self.assertEqual(
            task["content"],
            "Choose the correct option.\n\nOptions:\nA. correct\nB. wrong",
        )

        acknowledgement = write_result.write_answer_batch(
            model=self.model,
            payload={
                "responses": [
                    {
                        "qa_id": task["qa_id"],
                        "question_path": task["question_path"],
                        "issued_at": task["issued_at"],
                        "raw_response": "'''answer\nA\n'''",
                        "attempts": 1,
                    }
                ]
            },
            question_root=self.question_root,
            result_root=self.result_root,
        )
        self.assertEqual(acknowledgement["written"], 1)

        result = self._read_result(relative_path)
        self.assertEqual(
            set(result["model_response"]),
            {
                "model",
                "raw_response",
                "answer",
                "status",
                "attempts",
                "finished_at",
                "elapsed_seconds",
            },
        )
        self.assertEqual(result["model_response"]["model"], self.model)
        self.assertNotIn("config_name", result["model_response"])
        self.assertEqual(
            set(result["evaluation"]),
            {"method", "expected_answer", "is_correct", "status"},
        )
        self.assertTrue(result["evaluation"]["is_correct"])

        repeated = write_result.write_answer_batch(
            model=self.model,
            payload={
                "responses": [
                    {
                        "qa_id": task["qa_id"],
                        "question_path": task["question_path"],
                        "issued_at": task["issued_at"],
                        "raw_response": "'''answer\nB\n'''",
                        "attempts": 1,
                    }
                ]
            },
            question_root=self.question_root,
            result_root=self.result_root,
        )
        self.assertEqual(repeated["written"], 0)
        self.assertEqual(self._read_result(relative_path)["model_response"]["answer"], "A")

    def test_l3_answer_then_expert_judge(self) -> None:
        relative_path = "L3/DG1/acoustic/q2.json"
        rubric = [{"key": "includes value", "weight": 1.0}]
        self._write_question(
            relative_path,
            {
                "qa_id": "L3_test_002",
                "type": "DG1",
                "layer": "L3",
                "question": "Give a quantitative design.",
                "reference_answer": "Use 1 kHz.",
                "rubric": rubric,
            },
        )

        answer_batch = read_task.read_answer_tasks(
            model=self.model,
            limit=32,
            question_root=self.question_root,
            result_root=self.result_root,
        )
        answer_task = answer_batch["tasks"][0]
        write_result.write_answer_batch(
            model=self.model,
            payload={
                "responses": [
                    {
                        "qa_id": answer_task["qa_id"],
                        "question_path": answer_task["question_path"],
                        "issued_at": answer_task["issued_at"],
                        "raw_response": "'''answer\nUse 1 kHz.\n'''",
                        "attempts": 1,
                    }
                ]
            },
            question_root=self.question_root,
            result_root=self.result_root,
        )
        pending_result = self._read_result(relative_path)
        self.assertEqual(
            pending_result["evaluation"],
            {
                "method": "expert_rubric_judge",
                "judge_model": "current-dialogue-model",
                "status": "pending",
                "attempts": 0,
            },
        )

        judge_batch = read_task.read_judge_tasks(
            model=self.model,
            limit=32,
            question_root=self.question_root,
            result_root=self.result_root,
        )
        self.assertEqual(len(judge_batch["tasks"]), 1)
        judge_task = judge_batch["tasks"][0]
        self.assertEqual(
            judge_task["payload"],
            {
                "question": "Give a quantitative design.",
                "reference_answer": "Use 1 kHz.",
                "rubric": rubric,
                "candidate_answer": "Use 1 kHz.",
                "candidate_answer_status": "success",
            },
        )

        judge_response = {
            "score": 1.0,
            "per_rubric": [
                {"key": "includes value", "score": 1.0, "reasoning": "Present."}
            ],
            "reasoning": "Fully correct.",
        }
        raw_judge_response = json.dumps(judge_response, ensure_ascii=False)
        acknowledgement = write_result.write_judge_batch(
            model=self.model,
            payload={
                "responses": [
                    {
                        "qa_id": judge_task["qa_id"],
                        "question_path": judge_task["question_path"],
                        "raw_response": raw_judge_response,
                        "attempts": 1,
                    }
                ]
            },
            question_root=self.question_root,
            result_root=self.result_root,
        )
        self.assertEqual(acknowledgement["written"], 1)

        result = self._read_result(relative_path)
        self.assertEqual(
            set(result["evaluation"]),
            {
                "method",
                "judge_model",
                "raw_response",
                "result",
                "status",
                "attempts",
                "finished_at",
            },
        )
        self.assertNotIn("judge_config_name", result["evaluation"])
        self.assertEqual(result["evaluation"]["raw_response"], raw_judge_response)
        self.assertEqual(result["evaluation"]["result"], judge_response)
        self.assertEqual(result["evaluation"]["status"], "success")

    def test_dg3_is_excluded_and_batch_limit_is_enforced(self) -> None:
        self._write_question(
            "L3/DG3/aviation/q3.json",
            {
                "qa_id": "L3_DG3_test_003",
                "type": "DG3",
                "layer": "L3",
                "question": "Build a model.",
                "reference_answer": "Model.",
                "rubric": [],
            },
        )
        batch = read_task.read_answer_tasks(
            model=self.model,
            limit=32,
            question_root=self.question_root,
            result_root=self.result_root,
        )
        self.assertEqual(batch["tasks"], [])
        with self.assertRaisesRegex(ValueError, "between 1 and 32"):
            read_task.read_answer_tasks(
                model=self.model,
                limit=33,
                question_root=self.question_root,
                result_root=self.result_root,
            )
        with self.assertRaisesRegex(ValueError, "at most 32"):
            write_result.write_answer_batch(
                model=self.model,
                payload={"responses": [{} for _ in range(33)]},
                question_root=self.question_root,
                result_root=self.result_root,
            )

    def test_parse_errors_follow_test_api_states(self) -> None:
        relative_path = "L1/BK1/mechanism/q4.json"
        self._write_question(
            relative_path,
            {
                "qa_id": "L1_test_004",
                "type": "BK1",
                "layer": "L1",
                "question": "Pick one.",
                "options": {"A": "answer", "B": "other"},
                "answer": "A",
            },
        )
        task = read_task.read_answer_tasks(
            model=self.model,
            limit=1,
            question_root=self.question_root,
            result_root=self.result_root,
        )["tasks"][0]
        write_result.write_answer_batch(
            model=self.model,
            payload={
                "responses": [
                    {
                        "qa_id": task["qa_id"],
                        "question_path": task["question_path"],
                        "issued_at": task["issued_at"],
                        "raw_response": "A without delimiters",
                    }
                ]
            },
            question_root=self.question_root,
            result_root=self.result_root,
        )
        result = self._read_result(relative_path)
        self.assertIsNone(result["model_response"]["answer"])
        self.assertEqual(result["model_response"]["status"], "answer_parse_error")
        self.assertFalse(result["evaluation"]["is_correct"])


if __name__ == "__main__":
    unittest.main()
