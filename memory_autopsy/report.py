"""Aggregate metrics and human-readable reports for an autopsy.

Rates are plain fractions over the trace, never model scores:

- ``stale_read_rate`` — stale reads / all reads.
- ``poison_influence_rate`` — incorrect decisions whose decisive
  record was poisoned / all incorrect decisions.
- ``contradiction_rate`` — decisions that read a contradicted record
  / all decisions.
- ``unused_rate`` / ``superseded_rate`` — share of records with that
  verdict.
- ``redundant_decision_rate`` — decisions no single removal flips /
  all decisions that read anything.
- ``decisive_recovery`` — decisions whose decisive (rank-1) record
  the autopsy recovered / all decisions that read anything. The
  rank-1 record is observed in the trace, so this validates the
  attribution plumbing, not a guess.
"""

from __future__ import annotations

import json

from memory_autopsy.attribution import decisive_record
from memory_autopsy.diagnosis import VERDICTS, diagnose_trace
from memory_autopsy.models import Trace


def aggregate(trace: Trace, autopsy: dict | None = None) -> dict:
    """Aggregate metrics for a trace (runs the autopsy if not given)."""
    if autopsy is None:
        autopsy = diagnose_trace(trace)
    verdicts = autopsy["verdicts"]
    counts = {v: 0 for v in VERDICTS}
    for verdict in verdicts.values():
        counts[verdict["verdict"]] += 1
    total_records = max(len(trace.records), 1)
    total_reads = max(len(trace.reads), 1)
    decisions = list(trace.decisions.values())
    incorrect = [d for d in decisions if d.outcome == "incorrect"]
    with_reads = [d for d in decisions if trace.reads_for(d.decision_id)]

    poisoned_incorrect = sum(
        1
        for d in incorrect
        if decisive_record(trace, d) is not None
        and verdicts[decisive_record(trace, d)]["verdict"] == "poisoned"
    )
    contradicted_decisions = sum(
        1
        for d in decisions
        if any(
            verdicts[r.record_id]["verdict"] == "contradicted"
            for r in trace.reads_for(d.decision_id)
        )
    )
    redundant = sum(
        1 for d in with_reads if autopsy["attributions"][d.decision_id]["redundant"]
    )
    recovered = sum(
        1
        for d in with_reads
        if autopsy["attributions"][d.decision_id]["decisive_record"] is not None
    )
    return {
        "records": len(trace.records),
        "reads": len(trace.reads),
        "decisions": len(decisions),
        "verdict_counts": counts,
        "stale_read_rate": autopsy["stale_reads"] / total_reads,
        "stale_reads": autopsy["stale_reads"],
        "poison_influence_rate": poisoned_incorrect / max(len(incorrect), 1),
        "poison_influenced_decisions": poisoned_incorrect,
        "incorrect_decisions": len(incorrect),
        "contradiction_rate": contradicted_decisions / max(len(decisions), 1),
        "contradicted_decisions": contradicted_decisions,
        "unused_rate": counts["unused"] / total_records,
        "superseded_rate": counts["superseded"] / total_records,
        "redundant_decision_rate": redundant / max(len(with_reads), 1),
        "redundant_decisions": redundant,
        "decisive_recovery": recovered / max(len(with_reads), 1),
    }


def markdown_report(trace: Trace, autopsy: dict | None = None) -> str:
    """A short Markdown autopsy report."""
    if autopsy is None:
        autopsy = diagnose_trace(trace)
    metrics = aggregate(trace, autopsy)
    lines = [
        "# Memory Autopsy Report",
        "",
        "Records: %d | Reads: %d | Decisions: %d"
        % (metrics["records"], metrics["reads"], metrics["decisions"]),
        "",
        "## Rates",
        "",
        "- Stale-read rate: %.3f (%d of %d reads)"
        % (metrics["stale_read_rate"], metrics["stale_reads"], metrics["reads"]),
        "- Poison-influence rate: %.3f (%d of %d incorrect decisions)"
        % (
            metrics["poison_influence_rate"],
            metrics["poison_influenced_decisions"],
            metrics["incorrect_decisions"],
        ),
        "- Contradiction rate: %.3f (%d of %d decisions)"
        % (
            metrics["contradiction_rate"],
            metrics["contradicted_decisions"],
            metrics["decisions"],
        ),
        "- Redundant-decision rate: %.3f (%d decisions no single removal flips)"
        % (metrics["redundant_decision_rate"], metrics["redundant_decisions"]),
        "- Decisive-record recovery: %.3f" % metrics["decisive_recovery"],
        "",
        "## Verdicts",
        "",
    ]
    for verdict in VERDICTS:
        count = metrics["verdict_counts"][verdict]
        if count:
            lines.append("- %s: %d" % (verdict, count))
    lines.append("")
    lines.append("## Blame (per decision)")
    lines.append("")
    for decision_id, attribution in sorted(autopsy["attributions"].items()):
        lines.append(
            "- %s: chose %r (%s); decisive=%s; causal=%s; redundant=%s"
            % (
                decision_id,
                attribution["chosen"],
                attribution["outcome"],
                attribution["decisive_record"],
                ",".join(attribution["causal_records"]) or "-",
                attribution["redundant"],
            )
        )
    lines.append("")
    lines.append("## Per-record verdicts")
    lines.append("")
    for record_id, verdict in sorted(autopsy["verdicts"].items()):
        lines.append(
            "- %s: %s — %s" % (record_id, verdict["verdict"], verdict["reason"])
        )
    return "\n".join(lines) + "\n"


def json_report(trace: Trace, autopsy: dict | None = None) -> str:
    """The full autopsy as JSON (metrics + verdicts + attributions)."""
    if autopsy is None:
        autopsy = diagnose_trace(trace)
    return json.dumps(
        {"metrics": aggregate(trace, autopsy), "autopsy": autopsy},
        indent=2,
        sort_keys=True,
    )
