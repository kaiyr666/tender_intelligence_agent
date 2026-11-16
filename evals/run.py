"""Run the eval set: uv run python -m evals.run

Each line of evals/cases.jsonl is {"id", "input", "expected": {field: value}}.
Every expected field is compared with the pipeline's output. Results go to
evals/results/latest.json; a summary table is printed for docs/EVAL.md.
"""

import json
import time
from collections import defaultdict
from pathlib import Path

from app.pipeline import run

CASES = Path(__file__).parent / "cases.jsonl"
RESULTS = Path(__file__).parent / "results" / "latest.json"


def matches(expected, actual) -> bool:
    """Exact match, with a small tolerance for numbers. Change per field if needed."""
    if isinstance(expected, int | float) and isinstance(actual, int | float):
        return abs(expected - actual) <= 1e-6 * max(1, abs(expected))
    return expected == actual


def main() -> None:
    cases = [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]
    per_field = defaultdict(lambda: [0, 0])  # field -> [correct, total]
    rows, failures = [], []

    for case in cases:
        try:
            output = run(case["input"])
        except Exception as error:  # an eval should report crashes, not stop on them
            output = {"_error": str(error)}
        correct = True
        for field, expected in case["expected"].items():
            hit = matches(expected, output.get(field))
            per_field[field][0] += hit
            per_field[field][1] += 1
            if not hit:
                correct = False
                failures.append(
                    {
                        "id": case["id"],
                        "field": field,
                        "expected": expected,
                        "got": output.get(field),
                    }
                )
        rows.append({"id": case["id"], "correct": correct, "output": output})

    summary = {
        "time": time.strftime("%Y-%m-%d %H:%M"),
        "cases": len(cases),
        "case_accuracy": round(sum(r["correct"] for r in rows) / max(1, len(rows)), 3),
        "field_accuracy": {f: round(c / t, 3) for f, (c, t) in per_field.items()},
    }
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps({**summary, "failures": failures, "rows": rows}, indent=2))

    print(f"Eval {summary['time']}: {summary['cases']} cases")
    print("\n| Metric | Score |\n|---|---|")
    print(f"| All fields correct | {summary['case_accuracy']:.0%} |")
    for field, score in summary["field_accuracy"].items():
        print(f"| {field} | {score:.0%} |")
    for failure in failures[:5]:
        print(
            f"- FAIL {failure['id']} {failure['field']}: expected {failure['expected']!r}, "
            f"got {failure['got']!r}"
        )


if __name__ == "__main__":
    main()
