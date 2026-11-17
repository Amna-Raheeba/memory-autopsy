"""Tests for the trace model and the JSONL loader."""

from __future__ import annotations

import pytest

from memory_autopsy.trace import load_trace, parse_event, trace_to_jsonl


def test_parse_write_event():
    event = parse_event(
        {
            "type": "write",
            "record_id": "r1",
            "key": "hotel",
            "value": "Hilton",
            "source": "agent",
            "t": 1,
            "supersedes": None,
        },
        line_no=1,
    )
    assert event.record_id == "r1"
    assert event.supersedes is None


def test_parse_read_and_decision_events():
    read = parse_event(
        {"type": "read", "decision_id": "d1", "record_id": "r1", "rank": 1, "t": 2},
        line_no=2,
    )
    assert read.rank == 1
    decision = parse_event(
        {
            "type": "decision",
            "decision_id": "d1",
            "key": "hotel",
            "chosen": "Hilton",
            "correct_value": "Hilton",
            "outcome": "correct",
            "t": 3,
        },
        line_no=3,
    )
    assert decision.outcome == "correct"


def test_parse_rejects_unknown_type_source_outcome():
    base = {"record_id": "r1", "key": "k", "value": "v", "source": "agent", "t": 1}
    with pytest.raises(ValueError, match="unknown event type"):
        parse_event({**base, "type": "explode"}, line_no=1)
    with pytest.raises(ValueError, match="unknown source"):
        parse_event({**base, "type": "write", "source": "ghost"}, line_no=1)
    with pytest.raises(ValueError, match="unknown outcome"):
        parse_event(
            {
                "type": "decision",
                "decision_id": "d1",
                "key": "k",
                "outcome": "maybe",
                "t": 1,
            },
            line_no=1,
        )


def test_parse_rejects_missing_field_and_bad_clock():
    with pytest.raises(ValueError, match="missing field"):
        parse_event({"type": "write", "record_id": "r1"}, line_no=4)
    with pytest.raises(ValueError, match="must be an integer"):
        parse_event(
            {
                "type": "write",
                "record_id": "r1",
                "key": "k",
                "value": "v",
                "source": "agent",
                "t": "soon",
            },
            line_no=5,
        )
    with pytest.raises(ValueError, match="supersedes"):
        parse_event(
            {
                "type": "write",
                "record_id": "r1",
                "key": "k",
                "value": "v",
                "source": "agent",
                "t": 1,
                "supersedes": 42,
            },
            line_no=6,
        )


def test_load_demo_trace(demo_trace):
    assert len(demo_trace.records) == 6
    assert len(demo_trace.reads) == 5
    assert len(demo_trace.decisions) == 3
    assert demo_trace.records["r1"].value == "Hilton"
    assert demo_trace.decisions["d1"].outcome == "incorrect"


def test_load_rejects_bad_json_and_duplicates(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"type": "write",\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 1: invalid JSON"):
        load_trace(bad)

    dup = tmp_path / "dup.jsonl"
    dup.write_text(
        '{"type": "write", "record_id": "r1", "key": "k", "value": "v", "source": "agent", "t": 1}\n'
        '{"type": "write", "record_id": "r1", "key": "k", "value": "w", "source": "agent", "t": 2}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate record_id"):
        load_trace(dup)


def test_load_rejects_dangling_references(tmp_path):
    dangling_read = tmp_path / "dangling.jsonl"
    dangling_read.write_text(
        '{"type": "read", "decision_id": "d1", "record_id": "rX", "rank": 1, "t": 1}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown record"):
        load_trace(dangling_read)

    dangling_super = tmp_path / "dangling2.jsonl"
    dangling_super.write_text(
        '{"type": "write", "record_id": "r1", "key": "k", "value": "v", "source": "agent", "t": 1, "supersedes": "rX"}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="supersedes unknown record"):
        load_trace(dangling_super)


def test_round_trip_preserves_trace(demo_trace, tmp_path):
    path = tmp_path / "roundtrip.jsonl"
    path.write_text(trace_to_jsonl(demo_trace), encoding="utf-8")
    reloaded = load_trace(path)
    assert len(reloaded.records) == len(demo_trace.records)
    assert len(reloaded.reads) == len(demo_trace.reads)
    assert len(reloaded.decisions) == len(demo_trace.decisions)
    assert reloaded.records["r4"].source == "untrusted"
    assert reloaded.decisions["d2"].chosen == "PK999"


def test_reads_for_sorted_by_rank(tb):
    tb.write("r1", "hotel", "A")
    tb.write("r2", "hotel", "B")
    tb.read("d1", "r2", 2)
    tb.read("d1", "r1", 1)
    tb.decide("d1", "hotel", "A", "A", "correct")
    assert [r.record_id for r in tb.trace.reads_for("d1")] == ["r1", "r2"]


def test_records_for_key_sorted_by_time(tb):
    tb.write("r2", "hotel", "B")
    tb.write("r1", "hotel", "A")
    assert [r.record_id for r in tb.trace.records_for_key("hotel")] == ["r2", "r1"]
