"""Model metadata and derived real-result tables used by the model figures."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import csv


FIG_ROOT = Path(__file__).resolve().parent
CACHE_ROOT = FIG_ROOT / "result_cache"


@dataclass(frozen=True)
class ModelMeta:
    label: str
    family: str
    release_date: date


MODEL_META: dict[str, ModelMeta] = {
    "deepseek-v3.1": ModelMeta("DeepSeek V3.1", "deepseek", date(2025, 8, 21)),
    "deepseek-v3.2": ModelMeta("DeepSeek V3.2", "deepseek", date(2025, 12, 1)),
    "gpt-5.2": ModelMeta("GPT-5.2", "chatgpt", date(2025, 12, 11)),
    "glm-4.7": ModelMeta("GLM-4.7", "glm", date(2025, 12, 22)),
    "MiniMax-M2.1": ModelMeta("MiniMax M2.1", "minimax", date(2025, 12, 23)),
    "kimi-k2.5": ModelMeta("Kimi K2.5", "kimi", date(2026, 1, 27)),
    "claude-opus-4.6": ModelMeta("Claude Opus 4.6", "claude", date(2026, 2, 5)),
    "glm-5": ModelMeta("GLM-5", "glm", date(2026, 2, 12)),
    "MiniMax-M2.5": ModelMeta("MiniMax M2.5", "minimax", date(2026, 2, 12)),
    "claude-sonnet-4-6": ModelMeta("Claude Sonnet 4.6", "claude", date(2026, 2, 17)),
    "glm-5.1": ModelMeta("GLM-5.1", "glm", date(2026, 4, 7)),
    "claude-opus-4-7": ModelMeta("Claude Opus 4.7", "claude", date(2026, 4, 16)),
    "kimi-k2.6": ModelMeta("Kimi K2.6", "kimi", date(2026, 4, 20)),
    "gpt-5.5": ModelMeta("GPT-5.5", "chatgpt", date(2026, 4, 23)),
    "deepseek-v4-flash": ModelMeta("DeepSeek V4 Flash", "deepseek", date(2026, 4, 24)),
    "qwen3.7-max": ModelMeta("Qwen3.7 Max", "qwen", date(2026, 5, 21)),
    "claude-opus-4-8": ModelMeta("Claude Opus 4.8", "claude", date(2026, 5, 28)),
    "qwen3.7-plus": ModelMeta("Qwen3.7 Plus", "qwen", date(2026, 6, 1)),
    "kimi-k2.7-code": ModelMeta("Kimi K2.7 Code", "kimi", date(2026, 6, 12)),
    "glm-5.2": ModelMeta("GLM-5.2", "glm", date(2026, 6, 16)),
    "claude-sonnet-5": ModelMeta("Claude Sonnet 5", "claude", date(2026, 6, 30)),
    "gpt-5.6-luna": ModelMeta("GPT-5.6 Luna", "chatgpt", date(2026, 7, 9)),
    "gpt-5.6-terra": ModelMeta("GPT-5.6 Terra", "chatgpt", date(2026, 7, 9)),
    "gpt-5.6-sol": ModelMeta("GPT-5.6 Sol", "chatgpt", date(2026, 7, 9)),
    "kimi-k3": ModelMeta("Kimi K3", "kimi", date(2026, 7, 16)),
    "qwen3.7-flash": ModelMeta("Qwen3.7 Flash", "qwen", date(2026, 7, 21)),
    "qwen3.8-max": ModelMeta("Qwen3.8 Max", "qwen", date(2026, 8, 2)),
    "deepseek-v4-pro-0813": ModelMeta("DeepSeek V4 Pro", "deepseek", date(2026, 8, 13)),
    "qwen3.8-flash": ModelMeta("Qwen3.8 Flash", "qwen", date(2026, 8, 26)),
}

EFFORT_SUFFIXES = ("-xhigh", "-max", "-mid", "-low")


def canonical_model(config_name: str) -> str:
    """Group GPT reasoning-effort configurations under one base model."""
    if config_name.startswith("gpt-"):
        for suffix in EFFORT_SUFFIXES:
            if config_name.endswith(suffix):
                return config_name[: -len(suffix)]
    return config_name


def read_csv(name: str) -> list[dict[str, str]]:
    path = CACHE_ROOT / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing real-result cache {path}. Run evaluation/figures/build_result_cache.py first."
        )
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def display_name(model: str) -> str:
    return MODEL_META[model].label


def release_order() -> list[str]:
    return sorted(MODEL_META, key=lambda key: (MODEL_META[key].release_date, MODEL_META[key].label))
