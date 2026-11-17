"""Shared fixtures for the memory-autopsy tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from memory_autopsy.models import Decision, ReadEvent, Record, Trace
from memory_autopsy.trace import load_trace

ROOT = Path(__file__).resolve().parent.parent


class TraceBuilder:
    """Build a Trace by hand, one event at a time, on a logical clock."""

    def __init__(self) -> None:
        self.trace = Trace()
        self.t = 0

    def write(self, rid, key, value, source="agent", supersedes=None):
        self.t += 1
        self.trace.records[rid] = Record(rid, key, value, source, self.t, supersedes)
        return rid

    def read(self, did, rid, rank):
        self.t += 1
        self.trace.reads.append(ReadEvent(did, rid, rank, self.t))

    def decide(self, did, key, chosen, correct, outcome):
        self.t += 1
        self.trace.decisions[did] = Decision(did, key, chosen, correct, outcome, self.t)


@pytest.fixture
def tb():
    return TraceBuilder()


@pytest.fixture
def demo_trace():
    return load_trace(ROOT / "examples" / "demo_trace.jsonl")
