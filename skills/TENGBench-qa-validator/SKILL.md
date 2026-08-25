---
name: TENGBench-qa-validator
description: "TENGBench validation. Triggered in phase=calibration: sample-check questions and write a marker notifying the orchestrator to assemble the benchmark."
---

# TENGBench-qa-validator

## Responsibilities

Quality gate during benchmark construction (the `calibration` phase). Manually sample-check question quality and use marker files to notify downstream assembly. Do not move any files; only write markers.

## Operating mode

Dispatch sub-agents by question type for concurrent sample checking (Task tool), wait for all sub-agents to finish, then write the completion marker at the root in a single step.

## Startup discipline

1. Work only in the current working directory and its descendants; never move upward.
2. At startup, check whether the `phase` in `state/master.json` is `calibration`. If not, report “Not yet in the validation phase” and exit.
3. Do not explore the project structure or read other agents' SKILL files or scripts.

## Permissions

- **Can read:** `papers/qualified/*/*/qa/*.json`, `state/master.json`
- **Can write:** pass/reject marker files under `papers/qualified/`
- **Prohibited:** calling any script; moving or deleting files; writing `state/master.json`; reading scripts or code from other modules.

## Workflow

### Step 1: Sample-check questions (with human assistance)

Sample 5–10% of each question type (glob `papers/qualified/*/*/qa/*.json`) and check:

- whether the question stem is ambiguous or incorrect;
- whether the correct choice is reasonable and the distractors would be valid in other scenarios;
- whether every DG rubric item is numerical and judgeable (purely qualitative descriptions must be corrected);
- whether `source_excerpt` genuinely comes from the paper and the citation is accurate.

For each sampled question, write a marker file in the same directory:

- **Pass (including pass after repair):** write a pass marker.
- **Unrepairable:** write a rejection marker.
- **Not sampled:** write no marker; downstream assembly treats it as passed by default.

### Step 2: Notify completion

After all sample-check markers have been written, write a completion marker at the benchmark root to notify downstream assembly that it may proceed.

## Termination conditions

- All sample-check markers have been written.
- The completion marker has been written.
- Output: “Validation complete; the completion marker has been written. Waiting for downstream benchmark assembly.”

## Output requirements

- Purely qualitative DG rubric items must be corrected before a pass marker is written.
