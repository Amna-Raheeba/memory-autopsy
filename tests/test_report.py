"""Tests for aggregate metrics and reports."""

from __future__ import annotations

import json

import pytest

from memory_autopsy.report import aggregate, json_report, markdown_report


def test_aggregate_demo_trace_numbers(demo_trace):
    metrics = aggregate(demo_trace)
    assert metrics["records"] == 6
    assert metrics["reads"] == 5
    assert metrics["decisions"] == 3
    assert metrics["stale_read_rate"] == pytest.approx(1 / 5)
    assert metrics["poison_influence_rate"] == pytest.approx(1 / 2)
    assert metrics["contradiction_rate"] == pytest.approx(0.0)
    assert metrics["decisive_recovery"] == pytest.approx(1.0)
    assert metrics["verdict_counts"]["poisoned"] == 1
    assert metrics["verdict_counts"]["stale"] == 1
    assert metrics["verdict_counts"]["overruled"] == 2
    assert metrics["verdict_counts"]["helpful"] == 1
    assert metrics["verdict_counts"]["unused"] == 1


def test_aggregate_empty_trace_does_not_crash(tb):
    metrics = aggregate(tb.trace)
    assert metrics["records"] == 0
    assert metrics["stale_read_rate"] == 0.0
    assert metrics["poison_influence_rate"] == 0.0
    assert metrics["decisive_recovery"] == 0.0


def test_markdown_report_contains_rates_and_blame(demo_trace):
    text = markdown_report(demo_trace)
    assert "Stale-read rate: 0.200" in text
    assert "Poison-influence rate: 0.500" in text
    assert "r1: stale" in text
    assert "r4: poisoned" in text
    assert "d1: chose 'Hilton' (incorrect)" in text


def test_json_report_round_trips(demo_trace):
    data = json.loads(json_report(demo_trace))
    assert data["metrics"]["records"] == 6
    assert data["autopsy"]["verdicts"]["r4"]["verdict"] == "poisoned"
    assert data["autopsy"]["attributions"]["d2"]["decisive_record"] == "r4"
