"""TENGBench evaluation entry point and command-line argument handling."""

import argparse

from src.main import run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TENGBench model evaluation.")
    parser.add_argument("--model", required=True, help="Tested model configuration name.")
    parser.add_argument(
        "--judge",
        help="Expert judge configuration name. Required when evaluating any L3 question.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(model_name=args.model, judge_name=args.judge)
