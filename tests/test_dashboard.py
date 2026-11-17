"""Tests for the dashboard helpers and the Streamlit app.

The AppTest is skipped when Streamlit is not installed (the bare
test venv has it, CI installs it).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

from dashboard.helpers import decision_table, demo_autopsy, example_traces, verdict_table  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")


def test_verdict_table_matches_demo():
    _trace, autopsy, _metrics = demo_autopsy()
    rows = {row["record"]: row["verdict"] for row in verdict_table(autopsy)}
    assert rows["r1"] == "stale"
    assert rows["r4"] == "poisoned"
    assert rows["r6"] == "unused"


def test_decision_table_shape():
    _trace, autopsy, _metrics = demo_autopsy()
    rows = decision_table(autopsy)
    assert len(rows) == 3
    by_id = {row["decision"]: row for row in rows}
    assert by_id["d1"]["decisive"] == "r1"
    assert by_id["d1"]["outcome"] == "incorrect"
    assert by_id["d3"]["outcome"] == "correct"


def test_example_traces_cover_all_scenarios():
    traces = example_traces()
    assert set(traces) == {"healthy", "stale", "poisoned", "contradictory", "mixed"}
    for scenario in ("healthy", "stale", "poisoned", "contradictory"):
        assert len(traces[scenario].decisions) == 5
    # Mixed has 5 mode decisions + 2 edge-case decisions.
    assert len(traces["mixed"].decisions) == 7


def test_dashboard_loads_with_no_exceptions():
    at = AppTest.from_file(APP)
    at.run(timeout=60)
    assert not at.exception


def test_dashboard_shows_demo_verdicts_and_evaluation():
    at = AppTest.from_file(APP)
    at.run(timeout=60)
    assert not at.exception
    # Tab 1: the demo blame report renders as dataframes.
    assert len(at.dataframe) >= 2
    verdicts = at.dataframe[0].value
    assert "stale" in [str(v) for v in verdicts["verdict"]]
    assert "poisoned" in [str(v) for v in verdicts["verdict"]]
    # Tab 2: the evaluation tab reads results/metrics.json.
    metrics = {m.label: str(m.value) for m in at.metric}
    assert metrics.get("Traces evaluated") == "250"
    assert metrics.get("Decisive-record recovery") == "1.000"
