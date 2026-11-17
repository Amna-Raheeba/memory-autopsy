"""Memory Autopsy: post-mortem diagnosis of an agent's memory system.

Given a trace of memory writes, reads and decisions, this package
attributes each decision to the specific memory records that shaped
it, and diagnoses memory-caused failures: stale records still being
read, contradicted records, superseded-but-still-read records, and
poisoned records.

Pure stdlib, deterministic, fully offline. No LLM, no network, no keys.
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "Amna Raheeba"

from memory_autopsy.diagnosis import diagnose_record, diagnose_trace
from memory_autopsy.models import Decision, ReadEvent, Record, Trace
from memory_autopsy.trace import load_trace

__all__ = [
    "__version__",
    "Decision",
    "ReadEvent",
    "Record",
    "Trace",
    "diagnose_record",
    "diagnose_trace",
    "load_trace",
]
