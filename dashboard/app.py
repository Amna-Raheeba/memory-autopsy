"""Memory Autopsy dashboard.

Tab 1 — Blame report: pick a scenario trace, see every record's
verdict and every decision's attribution (decisive record, causal
set, redundant flag).

Tab 2 — Evaluation: the headline numbers from results/metrics.json
(per-verdict precision/recall over the 250-trace seeded dataset),
with the scenario breakdown.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from dashboard.helpers import decision_table, demo_autopsy, example_traces, verdict_table
from memory_autopsy.diagnosis import diagnose_trace
from memory_autopsy.report import aggregate

ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(page_title="Memory Autopsy", layout="wide")
st.title("Memory Autopsy")
st.write(
    "Post-mortem diagnosis of an agent's memory: which records shaped "
    "which decisions, and which records were stale, contradicted, "
    "superseded, poisoned, or simply never read."
)

tab_blame, tab_eval = st.tabs(["Blame report", "Evaluation"])

with tab_blame:
    scenario = st.selectbox(
        "Trace",
        ["demo (stale-memory incident)", "healthy", "stale", "poisoned", "contradictory", "mixed"],
    )
    if scenario.startswith("demo"):
        _trace, autopsy, metrics = demo_autopsy()
    else:
        _trace = example_traces()[scenario]
        autopsy = diagnose_trace(_trace)
        metrics = aggregate(_trace, autopsy)

    col1, col2, col3 = st.columns(3)
    col1.metric("Records", metrics["records"])
    col2.metric("Stale-read rate", "%.3f" % metrics["stale_read_rate"])
    col3.metric("Poison-influence rate", "%.3f" % metrics["poison_influence_rate"])

    st.subheader("Per-record verdicts")
    st.dataframe(verdict_table(autopsy), width="stretch")
    st.subheader("Per-decision attribution")
    st.dataframe(decision_table(autopsy), width="stretch")

with tab_eval:
    metrics_path = ROOT / "results" / "metrics.json"
    if metrics_path.exists():
        evaluation = json.loads(metrics_path.read_text(encoding="utf-8"))
        st.metric("Traces evaluated", evaluation["traces"])
        st.metric(
            "Decisive-record recovery",
            "%.3f" % evaluation["decisive_recovery"],
        )
        st.subheader("Per-verdict precision / recall")
        rows = []
        for verdict, cell in evaluation["per_verdict"].items():
            if cell["tp"] + cell["fp"] + cell["fn"]:
                rows.append(
                    {
                        "verdict": verdict,
                        "precision": (
                            "n/a" if cell["precision"] is None else round(cell["precision"], 3)
                        ),
                        "recall": (
                            "n/a" if cell["recall"] is None else round(cell["recall"], 3)
                        ),
                        "tp": cell["tp"],
                        "fp": cell["fp"],
                        "fn": cell["fn"],
                    }
                )
        st.dataframe(rows, width="stretch")
        st.subheader("Decisive recovery by scenario")
        st.dataframe(
            [
                {
                    "scenario": name,
                    "traces": entry["traces"],
                    "decisive_recovery": round(entry["decisive_recovery"], 3),
                }
                for name, entry in evaluation["by_scenario"].items()
            ],
            width="stretch",
        )
    else:
        st.warning("results/metrics.json not found — run python scripts/reproduce_results.py first.")
