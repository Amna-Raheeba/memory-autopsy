"""The versioned store: what was true, and when, in a trace.

Supersession is EXPLICIT: a record is superseded only by a later
write that names it in ``supersedes``. A same-key write with no link
starts a parallel version — that is how contradictions survive in the
store instead of being silently overwritten, and it is why the
autopsy can tell a stale read (read after an explicit supersession)
from a contradiction (two live parallel versions).

Stale rule (the versioned-provenance detector): a read is stale when
the record it read had already been superseded at the read's time,
i.e. the superseding write's ``t`` is strictly before the read's
``t``. A read at the exact same tick as the superseding write is
NOT stale — the update and the read raced, and the autopsy does not
guess which won.
"""

from __future__ import annotations

from memory_autopsy.models import Record, Trace


class VersionedStore:
    """Derived store state over a trace: supersession chains, liveness."""

    def __init__(self, trace: Trace) -> None:
        self.trace = trace
        # record_id -> record that supersedes it (at most one superseder
        # in a well-formed trace; the latest wins if several link it).
        self.superseded_by: dict[str, str] = {}
        for record in trace.records.values():
            if record.supersedes is not None:
                previous = self.superseded_by.get(record.supersedes)
                if previous is None or record.t > trace.records[previous].t:
                    self.superseded_by[record.supersedes] = record.record_id

    def superseding_write(self, record_id: str) -> Record | None:
        """The record that supersedes this one, or None."""
        other_id = self.superseded_by.get(record_id)
        if other_id is None:
            return None
        return self.trace.records[other_id]

    def is_superseded_before(self, record_id: str, t: int) -> bool:
        """Was this record superseded strictly before time ``t``?"""
        other = self.superseding_write(record_id)
        return other is not None and other.t < t

    def is_stale_read(self, record_id: str, read_t: int) -> bool:
        """Was a read of this record at ``read_t`` a stale read?"""
        return self.is_superseded_before(record_id, read_t)

    def live_records(self, key: str, t: int) -> list[Record]:
        """Records for ``key`` written before ``t`` and not superseded before ``t``."""
        return [
            record
            for record in self.trace.records_for_key(key)
            if record.t < t and not self.is_superseded_before(record.record_id, t)
        ]

    def contradiction_pairs(self, key: str, t: int) -> list[tuple[Record, Record]]:
        """Live parallel versions of ``key`` that disagree.

        Two records contradict when they share a key, hold different
        values, are both live at ``t``, and neither supersedes the
        other. Supersession resolves a contradiction, so a superseded
        record never appears here.
        """
        live = self.live_records(key, t)
        pairs: list[tuple[Record, Record]] = []
        for i, first in enumerate(live):
            for second in live[i + 1:]:
                if first.value != second.value:
                    pairs.append((first, second))
        return pairs

    def contradiction_partners(
        self, record_id: str, t: int, read_ids: set[str]
    ) -> list[Record]:
        """Live contradiction partners of this record that were read
        by the SAME decision.

        A contradiction only matters to an autopsy when the agent
        actually saw both sides together. A record that merely shares
        a key with a leftover from an earlier episode is not
        "contradicted" — the store accumulates parallel versions
        across decisions, and blaming a later record for an earlier
        episode's conflict would flood the report.
        """
        record = self.trace.records[record_id]
        partners: list[Record] = []
        for first, second in self.contradiction_pairs(record.key, t):
            if first.record_id == record_id and second.record_id in read_ids:
                partners.append(second)
            elif second.record_id == record_id and first.record_id in read_ids:
                partners.append(first)
        return partners

    def has_contradiction(self, record_id: str, t: int) -> bool:
        """Is this record part of any live contradiction pair at ``t``?

        Global (store-wide) view — used by the blame graph, not by
        the verdict, which scopes contradictions to one decision.
        """
        record = self.trace.records[record_id]
        for first, second in self.contradiction_pairs(record.key, t):
            if first.record_id == record_id or second.record_id == record_id:
                return True
        return False

    def contradicts_trusted(self, record_id: str) -> Record | None:
        """A trusted record this record disagrees with, if any.

        The trusted partner must hold the value the LATEST labelled
        decision confirms as correct for this key — the current known
        truth, not a value that was correct in an earlier episode
        before the world changed. Without any labelled decision for
        the key, the structural clause cannot fire and only the
        drove-a-wrong-decision clause can mark a record poisoned.
        """
        record = self.trace.records[record_id]
        labelled = [
            d
            for d in self.trace.decisions.values()
            if d.key == record.key and d.outcome != "unknown" and d.correct_value is not None
        ]
        if not labelled:
            return None
        current_truth = max(labelled, key=lambda d: d.t).correct_value
        for other in self.trace.records_for_key(record.key):
            if (
                other.record_id != record_id
                and other.source in ("user", "agent", "tool")
                and other.value != record.value
                and other.value == current_truth
                and other.record_id not in self.superseded_by
                and record.record_id not in self.superseded_by
            ):
                return other
        return None
