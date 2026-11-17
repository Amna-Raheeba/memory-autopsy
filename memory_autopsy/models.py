"""Trace model: the three event kinds an autopsy reads.

A trace is a JSONL file, one event per line, on a logical clock ``t``
(an integer; wall-clock timestamps are never required):

- ``write``: a record enters memory. ``supersedes`` names the record
  this write explicitly replaces (explicit versioned provenance: a
  write with no ``supersedes`` link starts a parallel version, it
  does NOT implicitly supersede anything).
- ``read``: a decision retrieved a record, at retrieval ``rank`` 1..n.
- ``decision``: the agent chose a value for a key. ``chosen`` is the
  value it acted on (``null`` = it abstained / had no memory);
  ``correct_value`` is the ground-truth value at that time (``null``
  = the outcome is unknown, e.g. a real trace with no labels).

Sources are ``user`` | ``agent`` | ``tool`` | ``untrusted``.
Outcomes are ``correct`` | ``incorrect`` | ``unknown``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SOURCES = ("user", "agent", "tool", "untrusted")
OUTCOMES = ("correct", "incorrect", "unknown")


@dataclass(frozen=True)
class Record:
    """One memory record: a single (key, value) claim in the store."""

    record_id: str
    key: str
    value: str
    source: str
    t: int
    supersedes: str | None = None


@dataclass(frozen=True)
class ReadEvent:
    """One retrieval: a decision read a record at a given rank."""

    decision_id: str
    record_id: str
    rank: int
    t: int


@dataclass(frozen=True)
class Decision:
    """One decision: the agent chose a value for a key."""

    decision_id: str
    key: str
    chosen: str | None
    correct_value: str | None
    outcome: str
    t: int


@dataclass
class Trace:
    """A whole run: records, reads and decisions, in event order."""

    records: dict[str, Record] = field(default_factory=dict)
    reads: list[ReadEvent] = field(default_factory=list)
    decisions: dict[str, Decision] = field(default_factory=dict)

    def reads_for(self, decision_id: str) -> list[ReadEvent]:
        """Reads for one decision, in retrieval-rank order."""
        out = [r for r in self.reads if r.decision_id == decision_id]
        return sorted(out, key=lambda r: r.rank)

    def record_ids_read(self, decision_id: str) -> list[str]:
        return [r.record_id for r in self.reads_for(decision_id)]

    def decisions_for_key(self, key: str) -> list[Decision]:
        return sorted(
            (d for d in self.decisions.values() if d.key == key),
            key=lambda d: d.t,
        )

    def records_for_key(self, key: str) -> list[Record]:
        return sorted(
            (r for r in self.records.values() if r.key == key),
            key=lambda r: r.t,
        )
