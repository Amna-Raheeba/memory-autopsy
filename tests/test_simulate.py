"""Tests for the seeded simulator and its ground truth."""

from __future__ import annotations

import pytest

from memory_autopsy.diagnosis import diagnose_trace
from memory_autopsy.evaluate import score_trace
from memory_autopsy.simulate import SCENARIOS, generate_dataset, generate_trace
from memory_autopsy.trace import trace_to_jsonl


def test_deterministic_same_seed():
    first, _ = generate_trace("mixed", seed=7)
    second, _ = generate_trace("mixed", seed=7)
    assert trace_to_jsonl(first) == trace_to_jsonl(second)


def test_different_seeds_differ():
    first, _ = generate_trace("mixed", seed=7)
    second, _ = generate_trace("mixed", seed=8)
    assert trace_to_jsonl(first) != trace_to_jsonl(second)


def test_unknown_scenario_rejected():
    with pytest.raises(ValueError, match="unknown scenario"):
        generate_trace("haunted", seed=7)


def test_healthy_all_decisions_correct():
    trace, truth = generate_trace("healthy", seed=7)
    assert all(d.outcome == "correct" for d in trace.decisions.values())
    verdicts = {v["verdict"] for v in diagnose_trace(trace)["verdicts"].values()}
    assert "stale" not in verdicts
    assert "poisoned" not in verdicts
    assert "contradicted" not in verdicts


def test_stale_scenario_has_stale_verdicts_and_wrong_decisions():
    trace, truth = generate_trace("stale", seed=7)
    verdicts = [v["verdict"] for v in diagnose_trace(trace)["verdicts"].values()]
    assert verdicts.count("stale") == 5
    assert verdicts.count("overruled") == 5
    assert all(d.outcome == "incorrect" for d in trace.decisions.values())


def test_poisoned_scenario():
    trace, truth = generate_trace("poisoned", seed=7)
    verdicts = [v["verdict"] for v in diagnose_trace(trace)["verdicts"].values()]
    assert verdicts.count("poisoned") == 5
    assert all(d.outcome == "incorrect" for d in trace.decisions.values())


def test_contradictory_scenario():
    trace, truth = generate_trace("contradictory", seed=7)
    verdicts = [v["verdict"] for v in diagnose_trace(trace)["verdicts"].values()]
    assert verdicts.count("contradicted") == 5
    assert verdicts.count("overruled") == 5


def test_mixed_scenario_covers_edge_cases():
    trace, truth = generate_trace("mixed", seed=7)
    verdicts = {v["verdict"] for v in diagnose_trace(trace)["verdicts"].values()}
    assert "unresolved" in verdicts
    assert "unused" in verdicts
    assert "helpful" in verdicts
    assert len(verdicts) >= 6


def test_ground_truth_decisive_matches_rank_one_read():
    for scenario in SCENARIOS:
        trace, truth = generate_trace(scenario, seed=7)
        for decision_id, want in truth["decisive"].items():
            reads = trace.reads_for(decision_id)
            got = reads[0].record_id if reads else None
            assert got == want


def test_dataset_shape():
    dataset = generate_dataset(seed=7, per_scenario=50, n_decisions=5)
    assert len(dataset) == 250
    by_scenario = {}
    for scenario, _trace, _truth in dataset:
        by_scenario[scenario] = by_scenario.get(scenario, 0) + 1
    assert by_scenario == {s: 50 for s in SCENARIOS}


def test_generated_traces_score_perfectly():
    for scenario in SCENARIOS:
        trace, truth = generate_trace(scenario, seed=7)
        score = score_trace(trace, truth)
        assert score["decisive_recovery"] == 1.0
        for verdict, cell in score["per_verdict"].items():
            if cell["tp"] + cell["fp"] + cell["fn"]:
                assert cell["precision"] == 1.0
                assert cell["recall"] == 1.0
