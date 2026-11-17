"""Tests for diagnosis: every verdict, and the priority order."""

from __future__ import annotations

from memory_autopsy.diagnosis import diagnose_record, diagnose_trace
from memory_autopsy.store import VersionedStore


def _verdict(trace, record_id):
    return diagnose_record(trace, VersionedStore(trace), record_id)["verdict"]


def test_poisoned_decisive_for_wrong_decision(tb):
    tb.write("r1", "flight", "PK701", source="tool")
    tb.write("r2", "flight", "PK999", source="untrusted")
    tb.read("d1", "r2", 1)
    tb.read("d1", "r1", 2)
    tb.decide("d1", "flight", "PK999", "PK701", "incorrect")
    assert _verdict(tb.trace, "r2") == "poisoned"
    assert _verdict(tb.trace, "r1") == "overruled"


def test_poisoned_structural_even_when_unread(tb):
    tb.write("r1", "flight", "PK701", source="tool")
    tb.read("d1", "r1", 1)
    tb.decide("d1", "flight", "PK701", "PK701", "correct")
    tb.write("r2", "flight", "PK999", source="untrusted")
    assert _verdict(tb.trace, "r2") == "poisoned"


def test_untrusted_but_correct_is_helpful_not_poisoned(tb):
    tb.write("r1", "flight", "PK701", source="untrusted")
    tb.read("d1", "r1", 1)
    tb.decide("d1", "flight", "PK701", "PK701", "correct")
    assert _verdict(tb.trace, "r1") == "helpful"


def test_stale_read_after_supersession(tb):
    tb.write("r1", "hotel", "Hilton")
    tb.write("r2", "hotel", "Marriott", supersedes="r1")
    tb.read("d1", "r1", 1)
    tb.read("d1", "r2", 2)
    tb.decide("d1", "hotel", "Hilton", "Marriott", "incorrect")
    assert _verdict(tb.trace, "r1") == "stale"
    assert _verdict(tb.trace, "r2") == "overruled"


def test_read_before_supersession_is_not_stale(tb):
    tb.write("r1", "hotel", "Hilton")
    tb.read("d1", "r1", 1)
    tb.decide("d1", "hotel", "Hilton", "Hilton", "correct")
    tb.write("r2", "hotel", "Marriott", supersedes="r1")
    assert _verdict(tb.trace, "r1") == "helpful"


def test_contradicted_same_decision_both_sides(tb):
    tb.write("r1", "hotel", "Hilton")
    tb.write("r2", "hotel", "Marriott")
    tb.read("d1", "r1", 1)
    tb.read("d1", "r2", 2)
    tb.decide("d1", "hotel", "Hilton", "Marriott", "incorrect")
    assert _verdict(tb.trace, "r1") == "contradicted"
    assert _verdict(tb.trace, "r2") == "overruled"


def test_contradiction_scoped_to_one_decision(tb):
    # r1 and r2 conflict in the store, but the agent never saw them
    # together: r1 is helpful, r2 is misleading — neither is
    # "contradicted" by a leftover from another episode.
    tb.write("r1", "hotel", "Hilton")
    tb.read("d1", "r1", 1)
    tb.decide("d1", "hotel", "Hilton", "Hilton", "correct")
    tb.write("r2", "hotel", "Marriott")
    tb.read("d2", "r2", 1)
    tb.decide("d2", "hotel", "Marriott", "Hilton", "incorrect")
    assert _verdict(tb.trace, "r1") == "helpful"
    assert _verdict(tb.trace, "r2") == "misleading"


def test_helpful_decisive_for_correct_decision(tb):
    tb.write("r1", "hotel", "Hilton")
    tb.read("d1", "r1", 1)
    tb.decide("d1", "hotel", "Hilton", "Hilton", "correct")
    assert _verdict(tb.trace, "r1") == "helpful"


def test_misleading_plain_bad_trusted_write(tb):
    tb.write("r1", "hotel", "Hilton")
    tb.write("r2", "hotel", "Marriott", supersedes="r1")
    tb.read("d1", "r2", 1)
    tb.decide("d1", "hotel", "Marriott", "Hilton", "incorrect")
    assert _verdict(tb.trace, "r2") == "misleading"
    assert _verdict(tb.trace, "r1") == "superseded"


def test_bystander_wrong_value_not_decisive(tb):
    tb.write("r1", "hotel", "Hilton")
    tb.write("r2", "hotel", "Hilton")  # same wrong value: no contradiction
    tb.read("d1", "r1", 1)
    tb.read("d1", "r2", 2)
    tb.decide("d1", "hotel", "Hilton", "Marriott", "incorrect")
    assert _verdict(tb.trace, "r1") == "misleading"
    assert _verdict(tb.trace, "r2") == "bystander"


def test_unresolved_only_unknown_outcomes(tb):
    tb.write("r1", "hotel", "Hilton")
    tb.read("d1", "r1", 1)
    tb.decide("d1", "hotel", "Hilton", None, "unknown")
    assert _verdict(tb.trace, "r1") == "unresolved"


def test_superseded_never_read_after(tb):
    tb.write("r1", "hotel", "Hilton")
    tb.write("r2", "hotel", "Marriott", supersedes="r1")
    assert _verdict(tb.trace, "r1") == "superseded"


def test_unused_never_read(tb):
    tb.write("r1", "hotel", "Hilton")
    assert _verdict(tb.trace, "r1") == "unused"


def test_priority_poisoned_beats_stale(tb):
    tb.write("r1", "hotel", "Hilton", source="untrusted")
    tb.write("r2", "hotel", "Marriott", supersedes="r1")
    tb.read("d1", "r1", 1)
    tb.decide("d1", "hotel", "Hilton", "Marriott", "incorrect")
    assert _verdict(tb.trace, "r1") == "poisoned"


def test_priority_stale_beats_contradicted(tb):
    tb.write("r1", "hotel", "Hilton")
    tb.write("r2", "hotel", "Marriott", supersedes="r1")
    tb.write("r3", "hotel", "Hyatt")
    tb.read("d1", "r1", 1)
    tb.read("d1", "r2", 2)
    tb.read("d1", "r3", 3)
    tb.decide("d1", "hotel", "Hilton", "Marriott", "incorrect")
    assert _verdict(tb.trace, "r1") == "stale"
    assert _verdict(tb.trace, "r2") == "overruled"
    assert _verdict(tb.trace, "r3") == "contradicted"


def test_cross_key_read_does_not_change_verdict(tb):
    # r1 (hotel) was only ever read by a flight decision: for its own
    # key it is unused.
    tb.write("r1", "hotel", "Hilton")
    tb.read("d1", "r1", 1)
    tb.decide("d1", "flight", "PK701", "PK702", "incorrect")
    assert _verdict(tb.trace, "r1") == "unused"


def test_demo_trace_verdicts(demo_trace):
    autopsy = diagnose_trace(demo_trace)
    verdicts = {rid: v["verdict"] for rid, v in autopsy["verdicts"].items()}
    assert verdicts == {
        "r1": "stale",
        "r2": "overruled",
        "r3": "overruled",
        "r4": "poisoned",
        "r5": "helpful",
        "r6": "unused",
    }
    assert autopsy["stale_reads"] == 1
    assert autopsy["attributions"]["d1"]["decisive_record"] == "r1"
    assert autopsy["attributions"]["d1"]["causal_records"] == ["r1"]
