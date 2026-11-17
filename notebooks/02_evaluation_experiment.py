"""Notebook 02 — evaluation experiment: score the autopsy on the
seeded 250-trace dataset and check seed sensitivity.

Run from the repo root:

    python notebooks/02_evaluation_experiment.py

Prints per-verdict precision/recall, decisive-record recovery, the
four aggregate rates, and the same check on three more seeds
(1, 42, 123). Expected on every seed: every verdict class with
instances scores precision = recall = 1.000, decisive recovery
1.000. That is the rule-based tool agreeing with its own trace
contract on synthetic data — see README section 7 for what this
does and does not prove.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from memory_autopsy.diagnosis import diagnose_trace  # noqa: E402
from memory_autopsy.evaluate import score_dataset, score_trace  # noqa: E402
from memory_autopsy.report import aggregate  # noqa: E402
from memory_autopsy.simulate import generate_dataset  # noqa: E402


def run(seed: int) -> dict:
    dataset = generate_dataset(seed=seed, per_scenario=50, n_decisions=5)
    scored = [(s, score_trace(t, tr)) for s, t, tr in dataset]
    evaluation = score_dataset(scored)
    stale_reads = reads = poison_inf = incorrect = contra = decisions = 0
    redundant = with_reads = 0
    for _scenario, trace, _truth in dataset:
        autopsy = diagnose_trace(trace)
        metrics = aggregate(trace, autopsy)
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
    evaluation["rates"] = {
        "stale_read_rate": stale_reads / reads,
        "poison_influence_rate": poison_inf / incorrect,
        "contradiction_rate": contra / decisions,
        "redundant_decision_rate": redundant / with_reads,
    }
    evaluation["counts"] = {
        "traces": len(dataset),
        "records": sum(len(t.records) for _s, t, _tr in dataset),
        "reads": reads,
        "decisions": decisions,
    }
    return evaluation


def _fmt(value) -> str:
    return "n/a" if value is None else "%.3f" % value


def main() -> None:
    evaluation = run(seed=7)
    print("Seed 7 — %d traces, %d records, %d reads, %d decisions" % (
        evaluation["counts"]["traces"],
        evaluation["counts"]["records"],
        evaluation["counts"]["reads"],
        evaluation["counts"]["decisions"],
    ))
    print("Decisive-record recovery: %.3f (%d/%d)" % (
        evaluation["decisive_recovery"],
        evaluation["decisive_right"],
        evaluation["decisive_total"],
    ))
    for verdict, cell in evaluation["per_verdict"].items():
        if cell["tp"] + cell["fp"] + cell["fn"]:
            print("  %-13s P=%s R=%s (tp=%d fp=%d fn=%d)" % (
                verdict, _fmt(cell["precision"]), _fmt(cell["recall"]),
                cell["tp"], cell["fp"], cell["fn"],
            ))
    for name, rate in evaluation["rates"].items():
        print("  %s: %.4f" % (name, rate))
    print("Seed sensitivity (seeds 1, 42, 123):")
    for seed in (1, 42, 123):
        other = run(seed=seed)
        imperfect = [
            v for v, c in other["per_verdict"].items()
            if c["tp"] + c["fp"] + c["fn"]
            and (c["precision"] != 1.0 or c["recall"] != 1.0)
        ]
        print("  seed %d: decisive %.3f, imperfect verdicts: %s" % (
            seed, other["decisive_recovery"], imperfect or "none",
        ))


if __name__ == "__main__":
    main()
