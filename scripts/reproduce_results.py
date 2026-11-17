"""Reproduce every number in results/ from scratch, in one command.

Run from the repo root:

    python scripts/reproduce_results.py

Regenerates (all deterministic, seed 7, 250 traces):
  - results/traces_250.jsonl   the headline dataset (generated data;
    git-ignored, never pushed)
  - results/metrics.json      aggregate metrics + per-verdict scores
  - results/evaluation.csv    per-verdict precision/recall table
  - results/summary.md        markdown report of the headline run

Exits non-zero if any headline number differs from the values
documented in README.md and docs/metrics.md, so a silent drift is
caught instead of shipped.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from memory_autopsy.diagnosis import diagnose_trace  # noqa: E402
from memory_autopsy.evaluate import score_dataset, score_trace  # noqa: E402
from memory_autopsy.report import aggregate  # noqa: E402
from memory_autopsy.simulate import generate_dataset  # noqa: E402
from memory_autopsy.trace import trace_to_jsonl  # noqa: E402

RESULTS = ROOT / "results"

# Headline numbers, as documented in README.md / docs/metrics.md.
EXPECTED = {
    "traces": 250,
    "records": 2807,
    "reads": 2401,
    "decisions": 1350,
    "decisive_recovery": 1.0,
    "decisive_right": 1350,
    "stale_read_rate": 0.1249,
    "poison_influence_rate": 0.3179,
    "contradiction_rate": 0.2156,
    "redundant_decision_rate": 0.1163,
}
# Every verdict class with instances must score a perfect 1.000.
EXPECTED_VERDICTS = (
    "poisoned",
    "stale",
    "overruled",
    "contradicted",
    "helpful",
    "misleading",
    "unresolved",
    "superseded",
    "unused",
)


def main() -> int:
    dataset = generate_dataset(seed=7, per_scenario=50, n_decisions=5)
    scored = [(s, score_trace(t, tr)) for s, t, tr in dataset]
    evaluation = score_dataset(scored)

    stale_reads = reads = poison_inf = incorrect = 0
    contra = decisions = redundant = with_reads = 0
    records = 0
    for _scenario, trace, _truth in dataset:
        autopsy = diagnose_trace(trace)
        metrics = aggregate(trace, autopsy)
        records += metrics["records"]
        stale_reads += metrics["stale_reads"]
        reads += metrics["reads"]
        poison_inf += metrics["poison_influenced_decisions"]
        incorrect += metrics["incorrect_decisions"]
        contra += metrics["contradicted_decisions"]
        decisions += metrics["decisions"]
        redundant += metrics["redundant_decisions"]
        with_reads += sum(
            1 for d in trace.decisions.values() if trace.reads_for(d.decision_id)
        )
    rates = {
        "stale_read_rate": stale_reads / reads,
        "poison_influence_rate": poison_inf / incorrect,
        "contradiction_rate": contra / decisions,
        "redundant_decision_rate": redundant / with_reads,
    }
    metrics_out = {
        "traces": len(dataset),
        "records": records,
        "reads": reads,
        "decisions": decisions,
        "decisive_recovery": evaluation["decisive_recovery"],
        "decisive_right": evaluation["decisive_right"],
        "decisive_total": evaluation["decisive_total"],
        "rates": {name: round(rate, 4) for name, rate in rates.items()},
        "per_verdict": evaluation["per_verdict"],
        "by_scenario": evaluation["by_scenario"],
    }

    RESULTS.mkdir(exist_ok=True)
    with (RESULTS / "traces_250.jsonl").open("w", encoding="utf-8") as handle:
        for scenario, trace, _truth in dataset:
            handle.write("# scenario=%s\n" % scenario)
            handle.write(trace_to_jsonl(trace))
    (RESULTS / "metrics.json").write_text(
        json.dumps(metrics_out, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (RESULTS / "evaluation.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["verdict", "tp", "fp", "fn", "precision", "recall"])
        for verdict, cell in evaluation["per_verdict"].items():
            writer.writerow(
                [
                    verdict,
                    cell["tp"],
                    cell["fp"],
                    cell["fn"],
                    "" if cell["precision"] is None else round(cell["precision"], 4),
                    "" if cell["recall"] is None else round(cell["recall"], 4),
                ]
            )
    summary = [
        "# Memory Autopsy — headline evaluation (seed 7)",
        "",
        "250 traces (50 per scenario: healthy, stale, poisoned, "
        "contradictory, mixed), %d records, %d reads, %d decisions."
        % (records, reads, decisions),
        "",
        "- Decisive-record recovery: %.3f (%d/%d)"
        % (
            evaluation["decisive_recovery"],
            evaluation["decisive_right"],
            evaluation["decisive_total"],
        ),
    ]
    for name, rate in rates.items():
        summary.append("- %s: %.4f" % (name, rate))
    summary.append("")
    summary.append("Per-verdict precision / recall: 1.000 for every class with")
    summary.append("instances (see results/evaluation.csv).")
    (RESULTS / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    errors = []
    for key, want in EXPECTED.items():
        got = metrics_out.get(key, rates.get(key))
        if isinstance(want, float):
            if got is None or abs(got - want) > 0.00005:
                errors.append("%s: got %s, expected %s" % (key, got, want))
        elif got != want:
            errors.append("%s: got %s, expected %s" % (key, got, want))
    for verdict in EXPECTED_VERDICTS:
        cell = evaluation["per_verdict"][verdict]
        if cell["precision"] != 1.0 or cell["recall"] != 1.0:
            errors.append(
                "%s: P=%s R=%s (tp=%d fp=%d fn=%d)"
                % (
                    verdict,
                    cell["precision"],
                    cell["recall"],
                    cell["tp"],
                    cell["fp"],
                    cell["fn"],
                )
            )
    if errors:
        print("DRIFT DETECTED:")
        for error in errors:
            print("  " + error)
        return 1
    print("All headline numbers reproduced (seed 7, 250 traces).")
    print("  decisive recovery %.3f, stale-read rate %.4f," % (
        evaluation["decisive_recovery"], rates["stale_read_rate"]))
    print("  poison-influence rate %.4f, contradiction rate %.4f," % (
        rates["poison_influence_rate"], rates["contradiction_rate"]))
    print("  redundant-decision rate %.4f" % rates["redundant_decision_rate"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
