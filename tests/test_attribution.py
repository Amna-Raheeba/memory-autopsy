"""Tests for attribution: replay, influence, causal sets, blame graph."""

from __future__ import annotations

from memory_autopsy.attribution import (
    attribute_decision,
    blame_graph,
    causal_set,
    decisive_record,
    influence,
    is_redundant,
    replay_decision,
)


def _decision_with_two_reads(tb):
    """d1 read r1 (rank 1, value A) and r2 (rank 2, value B)."""
    tb.write("r1", "hotel", "A")
    tb.write("r2", "hotel", "B")
    tb.read("d1", "r1", 1)
    tb.read("d1", "r2", 2)
    tb.decide("d1", "hotel", "A", "A", "correct")
    return tb.trace.decisions["d1"]


def test_replay_removes_records(tb):
    decision = _decision_with_two_reads(tb)
    assert replay_decision(tb.trace, decision, frozenset()) == "A"
    assert replay_decision(tb.trace, decision, frozenset({"r1"})) == "B"
    assert replay_decision(tb.trace, decision, frozenset({"r2"})) == "A"
    assert replay_decision(tb.trace, decision, frozenset({"r1", "r2"})) is None


def test_influence_and_causal_set(tb):
    decision = _decision_with_two_reads(tb)
    assert influence(tb.trace, decision, "r1") is True
    assert influence(tb.trace, decision, "r2") is False
    assert causal_set(tb.trace, decision) == ["r1"]
    assert is_redundant(tb.trace, decision) is False


def test_redundant_when_rank_two_shares_the_value(tb):
    tb.write("r1", "hotel", "A")
    tb.write("r2", "hotel", "A")  # same value, parallel record
    tb.read("d1", "r1", 1)
    tb.read("d1", "r2", 2)
    tb.decide("d1", "hotel", "A", "A", "correct")
    decision = tb.trace.decisions["d1"]
    assert influence(tb.trace, decision, "r1") is False
    assert causal_set(tb.trace, decision) == []
    assert is_redundant(tb.trace, decision) is True
    assert decisive_record(tb.trace, decision) == "r1"


def test_decisive_record_none_without_reads(tb):
    tb.decide("d1", "hotel", None, "A", "incorrect")
    decision = tb.trace.decisions["d1"]
    assert decisive_record(tb.trace, decision) is None
    assert replay_decision(tb.trace, decision, frozenset()) is None
    assert causal_set(tb.trace, decision) == []
    assert is_redundant(tb.trace, decision) is False


def test_attribute_decision_shape(tb):
    decision = _decision_with_two_reads(tb)
    out = attribute_decision(tb.trace, decision)
    assert out["decision_id"] == "d1"
    assert out["decisive_record"] == "r1"
    assert out["causal_records"] == ["r1"]
    assert out["read_records"] == ["r1", "r2"]
    assert out["read_count"] == 2
    assert out["redundant"] is False


def test_blame_graph_nodes_edges_and_labels(demo_trace):
    graph = blame_graph(demo_trace)
    node_ids = {n["id"] for n in graph["nodes"]}
    assert node_ids == {"d1", "d2", "d3", "r1", "r2", "r3", "r4", "r5", "r6"}
    reads = [e for e in graph["edges"] if e["kind"] == "read"]
    assert len(reads) == 5
    d1_r1 = next(e for e in reads if e["from"] == "d1" and e["to"] == "r1")
    assert d1_r1["rank"] == 1 and d1_r1["causal"] is True
    d1_r2 = next(e for e in reads if e["from"] == "d1" and e["to"] == "r2")
    assert d1_r2["causal"] is False
    supersedes = [e for e in graph["edges"] if e["kind"] == "supersedes"]
    assert len(supersedes) == 1
    assert supersedes[0]["from"] == "r2" and supersedes[0]["to"] == "r1"
    # The demo trace HAS one same-decision contradiction pair: the
    # poison record r4 and the true record r3, both read by d2.
    # The graph shows the structural conflict; the verdicts (poisoned
    # for r4, overruled for r3) say what it meant.
    contradicts = [e for e in graph["edges"] if e["kind"] == "contradicts"]
    assert len(contradicts) == 1
    assert {contradicts[0]["from"], contradicts[0]["to"]} == {"r3", "r4"}


def test_blame_graph_contradicts_edge(tb):
    tb.write("r1", "hotel", "A")
    tb.write("r2", "hotel", "B")
    tb.read("d1", "r1", 1)
    tb.read("d1", "r2", 2)
    tb.decide("d1", "hotel", "A", "B", "incorrect")
    graph = blame_graph(tb.trace)
    contradicts = [e for e in graph["edges"] if e["kind"] == "contradicts"]
    assert len(contradicts) == 1
    assert {contradicts[0]["from"], contradicts[0]["to"]} == {"r1", "r2"}
