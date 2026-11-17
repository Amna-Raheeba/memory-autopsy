"""Tests for the versioned store: supersession, staleness, contradictions."""

from __future__ import annotations

from memory_autopsy.store import VersionedStore


def _store_with_supersession(tb):
    """r1 (old) superseded by r2 (new) at a later tick."""
    tb.write("r1", "hotel", "Hilton")
    tb.write("r2", "hotel", "Marriott", supersedes="r1")
    return VersionedStore(tb.trace)


def test_superseding_write_found_or_none(tb):
    store = _store_with_supersession(tb)
    assert store.superseding_write("r1").record_id == "r2"
    assert store.superseding_write("r2") is None


def test_superseded_before_boundary_is_strict(tb):
    store = _store_with_supersession(tb)
    superseder_t = tb.trace.records["r2"].t
    assert store.is_superseded_before("r1", superseder_t) is False
    assert store.is_superseded_before("r1", superseder_t + 1) is True


def test_stale_read_boundary(tb):
    store = _store_with_supersession(tb)
    superseder_t = tb.trace.records["r2"].t
    # A read at the exact tick of the superseding write raced it:
    # not stale. One tick later it is a stale read.
    assert store.is_stale_read("r1", superseder_t) is False
    assert store.is_stale_read("r1", superseder_t + 1) is True
    assert store.is_stale_read("r2", superseder_t + 100) is False


def test_live_records_exclude_superseded(tb):
    store = _store_with_supersession(tb)
    live = store.live_records("hotel", 100)
    assert [r.record_id for r in live] == ["r2"]
    live_early = store.live_records("hotel", tb.trace.records["r2"].t)
    assert [r.record_id for r in live_early] == ["r1"]


def test_contradiction_pairs_need_live_disagreement(tb):
    tb.write("r1", "hotel", "Hilton")
    tb.write("r2", "hotel", "Marriott")
    store = VersionedStore(tb.trace)
    pairs = store.contradiction_pairs("hotel", 100)
    assert len(pairs) == 1
    assert {p.record_id for p in pairs[0]} == {"r1", "r2"}


def test_contradiction_pairs_exclude_superseded(tb):
    # r1 is superseded by r2, so it cannot contradict anything live.
    tb.write("r1", "hotel", "Hilton")
    tb.write("r2", "hotel", "Marriott", supersedes="r1")
    store = VersionedStore(tb.trace)
    assert store.contradiction_pairs("hotel", 100) == []


def test_contradiction_partners_require_same_decision_reads(tb):
    tb.write("r1", "hotel", "Hilton")
    tb.write("r2", "hotel", "Marriott")
    tb.read("d1", "r1", 1)
    tb.read("d2", "r2", 1)
    tb.decide("d1", "hotel", "Hilton", "Hilton", "correct")
    tb.decide("d2", "hotel", "Marriott", "Hilton", "incorrect")
    store = VersionedStore(tb.trace)
    # r1's partner r2 was never read by the same decision as r1.
    assert store.contradiction_partners("r1", 100, {"r1"}) == []
    assert store.contradiction_partners("r1", 100, {"r1", "r2"}) != []


def test_contradicts_trusted_needs_latest_correct_value(tb):
    # Hilton was the correct value at d1's time; the world has since
    # moved to Marriott. An untrusted record holding the CURRENT truth
    # (Marriott) disagrees with the old Hilton record — but that
    # record no longer speaks for the truth, so it is not evidence
    # of poisoning. (The old "any correct value" rule flagged this.)
    tb.write("r1", "hotel", "Hilton", source="tool")
    tb.read("d1", "r1", 1)
    tb.decide("d1", "hotel", "Hilton", "Hilton", "correct")
    tb.write("r2", "hotel", "Marriott", source="agent")
    tb.read("d2", "r2", 1)
    tb.decide("d2", "hotel", "Marriott", "Marriott", "correct")
    tb.write("r3", "hotel", "Marriott", source="untrusted")
    store = VersionedStore(tb.trace)
    assert store.contradicts_trusted("r3") is None


def test_contradicts_trusted_finds_current_truth(tb):
    tb.write("r1", "hotel", "Marriott", source="tool")
    tb.read("d1", "r1", 1)
    tb.decide("d1", "hotel", "Marriott", "Marriott", "correct")
    tb.write("r2", "hotel", "Hilton", source="untrusted")
    store = VersionedStore(tb.trace)
    partner = store.contradicts_trusted("r2")
    assert partner is not None and partner.record_id == "r1"


def test_contradicts_trusted_none_without_labels(tb):
    tb.write("r1", "hotel", "Marriott", source="tool")
    tb.write("r2", "hotel", "Hilton", source="untrusted")
    store = VersionedStore(tb.trace)
    assert store.contradicts_trusted("r2") is None
