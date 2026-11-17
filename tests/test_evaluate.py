"""Tests for scoring against simulator ground truth."""

from __future__ import annotations

from memory_autopsy.evaluate import score_dataset, score_trace
from memory_autopsy.simulate import generate_dataset, generate_trace


def test_score_trace_perfect_on_generated_trace():
    trace, truth = generate_trace("mixed", seed=7)
    score = score_trace(trace, truth)
    assert score["decisive_recovery"] == 1.0
    assert score["decisive_right"] == score["decisive_total"]


def test_empty_verdict_class_reports_none_not_one():
    trace, truth = generate_trace("healthy", seed=7)
    score = score_trace(trace, truth)
    # No bystander exists anywhere in a healthy trace.
    cell = score["per_verdict"]["bystander"]
    assert cell["tp"] == 0 and cell["fp"] == 0 and cell["fn"] == 0
    assert cell["precision"] is None
    assert cell["recall"] is None


def test_score_dataset_aggregates():
    dataset = generate_dataset(seed=7, per_scenario=2, n_decisions=5)
    scored = [(s, score_trace(t, tr)) for s, t, tr in dataset]
    evaluation = score_dataset(scored)
    assert evaluation["traces"] == 10
    assert evaluation["decisive_recovery"] == 1.0
    assert set(evaluation["by_scenario"]) == {
        "healthy",
        "stale",
        "poisoned",
        "contradictory",
        "mixed",
    }
    for entry in evaluation["by_scenario"].values():
        assert entry["traces"] == 2
        assert entry["decisive_recovery"] == 1.0
