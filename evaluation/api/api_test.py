"""Check the configured model endpoints without creating any files."""

from __future__ import annotations

import concurrent.futures

from openai import OpenAI

from src.main import load_models
from src.worker import _client


TIMEOUT_SECONDS = 30.0
PREVIEW_LENGTH = 120
MAX_WORKERS = 16


def test_model(config_name: str, config: dict[str, object]) -> str:
    try:
        client: OpenAI = _client(config)
        response = client.chat.completions.create(
            model=config["model"],
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            timeout=TIMEOUT_SECONDS,
            extra_body={"enable_thinking": config["enable_thinking"]},
        )
        if isinstance(response, str):
            content = response
        else:
            content = response.choices[0].message.content or ""
        if content.lstrip().lower().startswith(("<!doctype html", "<html")):
            raise ValueError("Gateway returned HTML instead of a model response.")
        preview = content.strip().replace("\n", " ")[:PREVIEW_LENGTH]
        return (
            f"[OK] {config_name} | enable_thinking={config['enable_thinking']} | "
            f"response={preview!r}"
        )
    except Exception as error:
        return (
            f"[FAIL] {config_name} | enable_thinking={config.get('enable_thinking')} | "
            f"{type(error).__name__}: {error}"
        )


def main() -> None:
    models = load_models()
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(test_model, config_name, config)
            for config_name, config in models.items()
        ]
        for future in concurrent.futures.as_completed(futures):
            print(future.result())


if __name__ == "__main__":
    main()
