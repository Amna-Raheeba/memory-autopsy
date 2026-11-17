"""Dashboard helpers: load a trace and run the autopsy, no Streamlit
needed here so the logic stays testable without the dashboard."""

from __future__ import annotations

from pathlib import Path

from memory_autopsy.diagnosis import diagnose_trace
from memory_autopsy.report import aggregate
from memory_autopsy.simulate import generate_trace
from memory_autopsy.trace import load_trace

ROOT = Path(__file__).resolve().parent.parent


def load_demo_trace():
    """The bundled demo trace (a stale-memory incident)."""
    return load_trace(ROOT / "examples" / "demo_trace.jsonl")


def demo_autopsy():
    """(trace, autopsy, metrics) for the demo trace."""
    trace = load_demo_trace()
    autopsy = diagnose_trace(trace)
    return trace, autopsy, aggregate(trace, autopsy)


def verdict_table(autopsy):
    """Per-record verdict rows, ready for st.dataframe / st.table."""
    rows = []
    for record_id, verdict in sorted(autopsy["verdicts"].items()):
        rows.append(
            {
                "record": record_id,
                "verdict": verdict["verdict"],
                "reason": verdict["reason"],
            }
        )
    return rows


def decision_table(autopsy):
    """Per-decision attribution rows, ready for st.dataframe."""
    rows = []
    for decision_id, attribution in sorted(autopsy["attributions"].items()):
        rows.append(
            {
                "decision": decision_id,
                "key": attribution["key"],
                "chosen": attribution["chosen"],
                "outcome": attribution["outcome"],
                "decisive": attribution["decisive_record"],
                "causal": ", ".join(attribution["causal_records"]) or "-",
                "redundant": attribution["redundant"],
            }
        )
    return rows


def example_traces():
    """One small trace per scenario, for the dashboard's scenario picker."""
    return {
        scenario: generate_trace(scenario, seed=7, n_decisions=5)[0]
        for scenario in ("healthy", "stale", "poisoned", "contradictory", "mixed")
    }
