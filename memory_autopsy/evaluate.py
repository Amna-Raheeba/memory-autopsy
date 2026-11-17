"""Score an autopsy against simulator ground truth.

Per-verdict precision / recall over records, plus attribution
checks over decisions. A record whose intended verdict is missing
from the truth labels (the simulator only labels records it created
with an intent) is skipped, not counted as wrong.
"""

from __future__ import annotations

from memory_autopsy.attribution import decisive_record
from memory_autopsy.diagnosis import VERDICTS, diagnose_trace
from memory_autopsy.models import Trace


def score_trace(trace: Trace, truth: dict) -> dict:
    """Score one trace: per-verdict precision/recall + attribution."""
    autopsy = diagnose_trace(trace)
    diagnosed = {rid: v["verdict"] for rid, v in autopsy["verdicts"].items()}
    intended = truth.get("verdicts", {})

    per_verdict: dict[str, dict] = {}
    for verdict in VERDICTS:
        tp = sum(1 for rid, want in intended.items() if want == verdict and diagnosed.get(rid) == verdict)
        fp = sum(1 for rid, got in diagnosed.items() if got == verdict and intended.get(rid) != verdict)
        fn = sum(1 for rid, want in intended.items() if want == verdict and diagnosed.get(rid) != verdict)
        # No instances of this class on either side: not 1.0, not 0.0 —
        # undefined. Callers must skip it, not report a perfect score.
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        per_verdict[verdict] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
        }

    decisive_right = 0
    decisive_total = 0
    for decision_id, want in truth.get("decisive", {}).items():
        decision = trace.decisions[decision_id]
        if not trace.reads_for(decision_id):
            continue
        decisive_total += 1
        if decisive_record(trace, decision) == want:
            decisive_right += 1

    return {
        "per_verdict": per_verdict,
        "decisive_recovery": decisive_right / decisive_total if decisive_total else 1.0,
        "decisive_right": decisive_right,
        "decisive_total": decisive_total,
    }


def score_dataset(
    scored: list[tuple[str, dict]],
) -> dict:
    """Aggregate per-trace scores into one evaluation dict.

    ``scored`` is a list of (scenario, score_trace(...)) pairs.
    Precision/recall are micro-averaged over the whole dataset, and
    also reported per scenario for the verdict classes that scenario
    exercises.
    """
    total_tp: dict[str, int] = {v: 0 for v in VERDICTS}
    total_fp: dict[str, int] = {v: 0 for v in VERDICTS}
    total_fn: dict[str, int] = {v: 0 for v in VERDICTS}
    decisive_right = 0
    decisive_total = 0
    by_scenario: dict[str, dict] = {}
    for scenario, score in scored:
        entry = by_scenario.setdefault(
            scenario, {"traces": 0, "decisive_right": 0, "decisive_total": 0}
        )
        entry["traces"] += 1
        decisive_right += score["decisive_right"]
        decisive_total += score["decisive_total"]
        entry["decisive_right"] += score["decisive_right"]
        entry["decisive_total"] += score["decisive_total"]
        for verdict in VERDICTS:
            cell = score["per_verdict"][verdict]
            total_tp[verdict] += cell["tp"]
            total_fp[verdict] += cell["fp"]
            total_fn[verdict] += cell["fn"]

    per_verdict = {}
    for verdict in VERDICTS:
        tp, fp, fn = total_tp[verdict], total_fp[verdict], total_fn[verdict]
        per_verdict[verdict] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        }
    for scenario, entry in by_scenario.items():
        entry["decisive_recovery"] = (
            entry["decisive_right"] / entry["decisive_total"] if entry["decisive_total"] else 1.0
        )
    return {
        "traces": len(scored),
        "per_verdict": per_verdict,
        "decisive_recovery": decisive_right / decisive_total if decisive_total else 1.0,
        "decisive_right": decisive_right,
        "decisive_total": decisive_total,
        "by_scenario": by_scenario,
    }
