<p align="center">
  <img src="asset/logo.svg" alt="TENGBench logo" width="520">
</p>

<h1 align="center">TENGBench</h1>

<p align="center">
  A layered benchmark for evaluating large language models on triboelectric nanogenerator research.
</p>

<p align="center">
  <a href="README-ZH.md">中文</a> · <a href="#quick-start">Quick start</a> · <a href="#project-structure">Project structure</a>
</p>

## News

- 📊 **[2026/09/11]** Released the complete TENGBench dataset.
- 🚀 **[2026/09/01]** Released the TENGBench project source code.

## Full benchmark results

<p align="center">
  <img src="asset/benchmark-results.svg" alt="Complete TENGBench results across evaluated models" width="100%">
</p>

The figure above is the complete multi-model leaderboard. Put the final vector figure at `asset/benchmark-results.svg`; the README will display it automatically.

## Overview

TENGBench builds and evaluates a three-layer question set derived from triboelectric nanogenerator (TENG) papers:

- **L1 — Basic Knowledge:** mechanism and device fundamentals (`BK1`–`BK4`).
- **L2 — Research Practice:** paper-level analysis and application reasoning (`RP1`–`RP4`).
- **L3 — Deep Generation:** open-ended design and synthesis tasks (`DG1`–`DG3`). `DG3` is currently excluded from automated evaluation.

The repository contains source code, agent skills, tests, and safe configuration examples. Papers, generated questions, state, logs, credentials, and evaluation results stay local through `.gitignore`.

## Evaluated model configurations

| Family | Configurations represented in the evaluation setup | Reasoning setup |
| --- | --- | --- |
| GPT | GPT-5.2, GPT-5.5, GPT-5.6 Luna, Terra, and Sol | `low`, `mid`, `max`, and `xhigh` variants |
| Claude | Sonnet 4.6, Sonnet 5, Opus 4.6, 4.7, and 4.8 | Provider default |
| DeepSeek | V3.1, V3.2, V4 Flash, and V4 Pro 0813 | Provider default |
| Qwen | 3.7 Plus/Max/Flash and 3.8 Max/Flash | Provider default |
| Kimi | K2.5, K2.6, K2.7 Code, and K3 | Provider default |
| GLM | 4.7, 5, 5.1, and 5.2 | Provider default |
| MiniMax | M2.1 and M2.5 | Provider default |

Every runnable API entry in `evaluation/api/models.yaml` uses this schema:

```yaml
configuration-name:
  base_url: https://api.example.com/v1
  api_key_env: PROVIDER_API_KEY
  model: provider-model-id
  enable_thinking: false
```

The configuration name is also the result directory name. The tested model and the L3 judge can use different entries.

## Requirements

- Python 3.10 or newer
- An OpenAI-compatible chat-completions endpoint for API evaluation
- Codex with the repository skills installed for the agent-based workflows

## Quick start

Create an isolated Python environment and install the project dependencies:

```bash
git clone git@github.com:LMDHQ-0420/TENGBench.git
cd TENGBench
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Generate the QA benchmark

Create the local working directories, put source PDFs in `papers/inbox/`, and install or link the three skills in `qa-generation/skills/` into Codex. The orchestrator runs the pipeline scripts in this order:

```bash
python qa-generation/scripts/orchestrator/distribute_papers.py
# Run TENGBench-reviewer-writer in Codex for the distributed papers.
python qa-generation/scripts/orchestrator/collect_and_route.py
python qa-generation/scripts/orchestrator/update_master.py
# Run TENGBench-qa-validator in Codex when sample validation is wanted.
python qa-generation/scripts/orchestrator/assemble_benchmark.py
```

Generated benchmark questions are written to `benchmark/question/` and remain local.

### Run API evaluation

```bash
cp evaluation/api/models.example.yaml evaluation/api/models.yaml
export OPENAI_API_KEY="your-key"
python evaluation/api/api_test.py
python evaluation/api/run.py --model gpt-example --judge gpt-example
```

`--judge` is required when the benchmark contains L3 questions. Runs resume from completed question files and write local artifacts to `result/<configuration-name>/`.

### Run skill-based evaluation

Install the skills in `evaluation/skill/skills/` in Codex, then start the answer workflow with `tengbench-test-orchestrator`. After the model answers are saved, run `tengbench-judge-orchestrator` to score pending L3 responses. Both workflows use the guarded readers and writers under `evaluation/skill/scripts/`.

## Project structure

```text
TENGBench/
├── asset/                       # Public README assets
├── qa-generation/
│   ├── scripts/                 # Paper routing, QA validation, benchmark assembly
│   └── skills/                  # Orchestrator, reviewer/writer, QA validator
├── evaluation/
│   ├── api/                     # Concurrent API evaluator and contract tests
│   └── skill/                   # Codex skill evaluator, guarded I/O, tests
├── requirements.txt
├── README.md
└── README-ZH.md
```

The local workflow also creates `papers/`, `cache/`, `benchmark/`, `state/`, `logs/`, `result/`, `result-simulation/`, and `fig/`. These directories are intentionally absent from commits.

## Tests

```bash
python -m unittest discover -s evaluation/api/tests
python -m unittest discover -s evaluation/skill/tests
```

## Asset filenames

- Project logo: `asset/logo.svg`
- Complete multi-model results: `asset/benchmark-results.svg`
