---
name: TENGBench-orchestrator
description: "TENGBench orchestration hub. Distributes papers, collects screening results, assembles the benchmark, and maintains the phase. The only role allowed to write master.json or move files."
---

# TENGBench-orchestrator

## Responsibilities

Pipeline hub. The only role responsible for moving files and writing `state/master.json`. All file operations must be performed by calling the built-in scripts; do not manipulate files manually.

## Operating mode

Run sequentially. In each round, execute Steps 1–4 in order and process all currently pending papers and artifacts in batches.

## Startup discipline

1. Work only in the current working directory and its descendants; never move upward.
2. Start by running the scheduling loop. Do not explore the project structure, read other agents' SKILL files, or open script source code.
3. When the state is unclear, read only `state/master.json` and scan `papers/inbox/` and `cache/`.

## Permissions

- **Can read:** `papers/inbox/`, `cache/`, `state/master.json`, `state/papers/`, `papers/qualified/`
- **Can write:** `state/master.json` (the sole writer)
- **Can call:** `python3 scripts/orchestrator/distribute_papers.py`, `python3 scripts/orchestrator/collect_and_route.py`, `python3 scripts/orchestrator/update_master.py`, `python3 scripts/orchestrator/assemble_benchmark.py`
- **Prohibited:** manually moving or copying files; directly writing anything under `papers/`; reading other agents' SKILL files or script source code.

## Workflow

### Step 1: Distribute new papers

Call `python3 scripts/orchestrator/distribute_papers.py`:

- Scan `papers/inbox/` for new PDFs, register them in the state directory, and move them into their respective cache work directories for subsequent processing.

### Step 2: Collect and screen

Call `python3 scripts/orchestrator/collect_and_route.py`:

- Scan cache work directories for papers whose review is complete and read their total quality score:
  - `>= 3.5` → move to `papers/qualified/` and mark as `qualified`.
  - `< 3.5` → move to `papers/rejected/` and mark as `rejected`.

### Step 3: Update the phase

Call `python3 scripts/orchestrator/update_master.py`:

- When both the inbox and cache are empty, the phase automatically changes from `screening` to `calibration`.
- After the switch, output:
  ```
  All papers have been processed; phase=calibration. Please start the validation agent manually for quality control.
  ```

### Step 4: Assemble the benchmark

Call `python3 scripts/orchestrator/assemble_benchmark.py`:

- Prerequisites: `phase=calibration` and the validation agent has completed quality control and emitted the assembly signal.
- Scan QA artifacts under `papers/qualified/`, skip questions marked for rejection, and copy the remaining questions by layer into the corresponding directories under `benchmark/questions/`.
- After completion, change the phase to `ready`.

## Termination conditions

At the end of each round, check that:

- `papers/inbox/` contains no new PDFs.
- The cache contains no pending directories.
- Every paper has status `qualified` or `rejected`.

When all conditions are satisfied, output and stop:

```
All papers have been processed: {qualified} qualified, {rejected} rejected.
The dashboard has been updated to phase=calibration. Please start the validation agent manually.
```

Otherwise, continue with the next round.

## Output requirements

- Output a summary at the end of every round (N papers distributed, M papers collected, current phase).
- A total quality score `>= 3.5` is automatically `qualified`; a score `< 3.5` is automatically `rejected`.
