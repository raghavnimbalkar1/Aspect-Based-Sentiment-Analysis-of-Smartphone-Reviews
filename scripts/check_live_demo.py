"""Run written demo regressions against real local models, without touching research data."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from smartphone_absa.data import file_hash
from smartphone_absa.models.live import LIVE_ID
from smartphone_absa.models.registry import ModelRegistry, ModelUnavailable


def check_cases(registry: ModelRegistry, model_id: str, cases: list[dict]) -> dict:
    model = registry.get(model_id)
    checks = []
    for case in cases:
        result = model.analyse(case["text"])
        actual = {aspect.category: str(aspect.sentiment) for aspect in result.aspects}
        general = str(result.general_opinion.sentiment) if result.general_opinion else None
        evidence = [e for aspect in result.aspects for e in aspect.evidence]
        if result.general_opinion:
            evidence += result.general_opinion.evidence
        offsets_valid = all(case["text"][e.start : e.end] == e.text for e in evidence)
        passed = (
            result.supported
            and actual == case["aspects"]
            and (not case.get("general_sentiment") or general == case["general_sentiment"])
            and offsets_valid
        )
        checks.append(
            {
                "id": case["id"],
                "text": case["text"],
                "expected_aspects": case["aspects"],
                "actual_aspects": actual,
                "expected_general": case.get("general_sentiment"),
                "actual_general": general,
                "supported": result.supported,
                "offsets_valid": offsets_valid,
                "passed": passed,
            }
        )
    return {
        "model_id": model_id,
        "cases": checks,
        "passed": sum(row["passed"] for row in checks),
        "failed": sum(not row["passed"] for row in checks),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("examples/live_review_cases.json"))
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    parser.add_argument("--model", action="append")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or Path(
        "artifacts/demo-check/"
        + datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        + "/report.json"
    )
    if output.exists():
        parser.error("Output already exists. Choose a new report path.")
    try:
        import torch

        torch.set_num_threads(2)
        registry = ModelRegistry(args.artifacts)
        cases = json.loads(args.cases.read_text())["cases"]
        reports = [check_cases(registry, mid, cases) for mid in (args.model or [LIVE_ID])]
    except (ModelUnavailable, ImportError) as exc:
        print(f"Local model unavailable: {exc}\nRun make model-setup first.", file=sys.stderr)
        return 2
    report = {
        "kind": "written_live_demo_regressions",
        "scope": "Synthetic development checks, not independent model accuracy.",
        "research_data_read_or_modified": False,
        "cases_sha256": file_hash(args.cases),
        "models": reports,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    for result in reports:
        print(f"{result['model_id']}: {result['passed']}/{len(cases)} checks passed")
        for row in result["cases"]:
            if not row["passed"]:
                print(
                    f"  FAIL {row['id']}: {row['actual_aspects']}, general={row['actual_general']}"
                )
    print(f"Report: {output}")
    return 1 if any(result["failed"] for result in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
