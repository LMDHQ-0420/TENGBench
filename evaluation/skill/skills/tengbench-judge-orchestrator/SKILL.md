---
name: tengbench-judge-orchestrator
description: Run the skill-based TENGBench expert phase by reading pending L3 batches through the approved script, delegating rubric scoring to isolated subagents, and writing evaluation/api-compatible evaluations.
---

# TENGBench Judge Orchestrator

Run the expert-scoring phase from the repository root. The required `model` input only selects the tested results under `result/<model>/`; it does not name or select the expert model. The current conversation model is the expert model, and scoring subagents inherit it.

## Data boundary

- Never open, search, list, or edit `benchmark/question/` or `result/` directly.
- Use only `evaluation/skill/scripts/read_task.py` and `evaluation/skill/scripts/write_result.py` for question and result I/O.
- Do not score, revise, summarize, or supplement a candidate answer yourself.
- Run Python through the `tengbench` conda environment.

## Workflow

1. Read up to 32 pending L3 tasks:

   `conda run -n tengbench python evaluation/skill/scripts/read_task.py judge --model <model> --limit <limit>`

   `limit` defaults to 32 and must be between 1 and 32. For later batches, add `--after <next_cursor>` only after the preceding batch is fully acknowledged.

2. For each task, create one isolated subagent with `fork_turns="none"` and no model override. Tell it to read and follow `evaluation/skill/skills/tengbench-rubric-judge/SKILL.md`, then pass the task's `payload` verbatim. Do not offer scoring suggestions.

   Immediately after creation succeeds, add an immutable dispatch-ledger entry keyed by the returned subagent identifier. Its value must be the exact `qa_id` and `question_path` from that task, plus the current attempt count. One identifier maps to exactly one task. Never associate a response by completion order, list position, score content, or a manually reconstructed question identifier.

3. Use available concurrency slots, in waves when necessary. When a final message arrives, use its subagent identifier to look up the ledger entry and attach the unchanged message only to that entry. Reject an unknown identifier, duplicate final message, reused identifier, or task without a ledger entry; do not write that batch until the association is resolved.

   A subagent tool failure may be retried once. The retry receives a new identifier mapped to the same original task metadata, increments `attempts`, and becomes the only active attempt for that task. Do not repair or retry a successfully returned scoring message; the result writer must preserve parse failures exactly as `evaluation/api` does.

4. Build every response object from one completed ledger entry: copy `qa_id`, `question_path`, and `attempts` from its stored task metadata, and use that same subagent's final message as `raw_response`. Do not copy task metadata from another entry. Start:

   `conda run -n tengbench python evaluation/skill/scripts/write_result.py judge --model <model>`

   Send one JSON line on stdin containing at most 32 raw subagent messages:

   `{"responses":[{"qa_id":"...","question_path":"...","raw_response":"...","attempts":1}]}`

   Use a JSON serializer and never put raw scoring output in shell arguments.

5. Continue through `next_cursor` while `has_more` is true. Then call:

   `conda run -n tengbench python evaluation/skill/scripts/read_task.py status --model <model>`

Completion requires `awaiting_judge` to be zero. The script records `judge_model` as `current-dialogue-model`; the `model` input remains solely the tested-result directory selector.
