#!/usr/bin/env python3
"""Rebuild real-result caches and render every TENGBench figure."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys


FIG_ROOT = Path(__file__).resolve().parent


def run(script: Path) -> None:
    subprocess.run([sys.executable, str(script)], cwd=FIG_ROOT.parents[1], check=True)


def main() -> None:
    # Always refresh derived tables first so result-driven figures cannot use
    # stale values after result files change.
    run(FIG_ROOT / "build_result_cache.py")
    figure_dirs = sorted(
        path for path in FIG_ROOT.iterdir()
        if path.is_dir() and re.match(r"^(?:\d{2}[a-z]?|S\d{2})_", path.name)
    )
    scripts = [
        script
        for folder in figure_dirs
        for script in sorted(folder.glob("plot_*.py"))
    ]
    for script in scripts:
        run(script)
    print(f"Rendered {len(scripts)} figures from current benchmark/result data.")


if __name__ == "__main__":
    main()
