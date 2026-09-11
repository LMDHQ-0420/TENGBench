---
name: tengbench-test-orchestrator
description: Run the skill-based TENGBench answer phase by reading bounded question batches through the approved script, delegating one question per isolated subagent, and writing API-compatible results through the approved script.
---

# TENGBench Test Orchestrator

Run the answer phase from the repository root. The required `model` input is only the directory selector for `result/<model>/`; it must never select or override an agent model. The current conversation model is the tested model, and answer subagents inherit it.

## Data boundary

- Never open, search, list, or edit `benchmark/question/` or `result/` directly.
- Use only `evaluation/skill/scripts/read_task.py` and `evaluation/skill/scripts/write_result.py` for question and result I/O.
- Do not inspect answers, reference answers, rubrics, or existing result JSON with any other tool.
- Run Python through the `tengbench` conda environment.

## Inputs

- `model`: required result-directory name.
- `limit`: optional batch size, default 32, range 1–32. Never process or write more than 32 questions in one batch.

## Workflow

1. Read a batch:

   `conda run -n tengbench python evaluation/skill/scripts/read_task.py answer --model <model> --limit <limit>`

   For later batches, add `--after <next_cursor>` only after every task in the previous batch was written or explicitly skipped by the writer.

2. For each returned task, create one isolated subagent with `fork_turns="none"` and no model override. Tell it to read and follow `evaluation/skill/skills/tengbench-answerer/SKILL.md`, then provide the task's `qa_id`, `is_objective`, and `content` verbatim. Do not summarize, solve, hint, or augment the question.

   Immediately after creation succeeds, add an immutable dispatch-ledger entry keyed by the returned subagent identifier. Its value must be the exact `qa_id`, `question_path`, and `issued_at` from that task, plus the current attempt count. One identifier maps to exactly one task. Never associate a response by completion order, list position, answer text, or a manually reconstructed question identifier.

3. Run as many answer subagents concurrently as available slots permit. A batch may contain up to 32 tasks even when it must run in several concurrency waves. When a final message arrives, use its subagent identifier to look up the ledger entry and attach the unchanged message only to that entry. Reject an unknown identifier, duplicate final message, reused identifier, or task without a ledger entry; do not write that batch until the association is resolved.

   A subagent tool failure may be retried once. The retry receives a new identifier mapped to the same original task metadata, increments the attempt count, and becomes the only active attempt for that task. Do not retry a successfully returned but malformed answer.

4. Build every response object from one completed ledger entry: copy `qa_id`, `question_path`, `issued_at`, and `attempts` from its stored task metadata, and use that same subagent's final message as `raw_response`. Do not copy task metadata from another entry. Start:

   `conda run -n tengbench python evaluation/skill/scripts/write_result.py answer --model <model>`

   Send exactly one JSON line on stdin:

   `{"responses":[{"qa_id":"...","question_path":"...","issued_at":"...","raw_response":"...","attempts":1}]}`

   Use a JSON serializer; never interpolate a raw answer into a shell command. Include at most 32 response objects.

5. Advance to `next_cursor` only when the writer acknowledges the entire batch. Continue while `has_more` is true. At the end, call:

   `conda run -n tengbench python evaluation/skill/scripts/read_task.py status --model <model>`

6. Completion requires `awaiting_answer` to be zero. L3 entries may remain in `awaiting_judge`; those belong to the expert phase.

The writer intentionally preserves `answer_parse_error` without a semantic retry so result behavior matches `evaluation/api`.
