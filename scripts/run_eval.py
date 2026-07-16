import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.metrics import EvalSummary, fetch_eval_summary


def print_summary(summary: EvalSummary, pretty: bool) -> None:
    payload = asdict(summary)
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize RouteWise request logs.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = asyncio.run(fetch_eval_summary())
    print_summary(summary, pretty=args.pretty)


if __name__ == "__main__":
    main()
