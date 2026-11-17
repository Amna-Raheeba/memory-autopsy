"""Load and validate a trace from a JSONL file.

Every line is one event (``write`` / ``read`` / ``decision``). A bad
line fails loudly with its line number instead of being skipped: an
autopsy that silently drops events would blame the wrong records.
"""

from __future__ import annotations

import json
from pathlib import Path

from memory_autopsy.models import OUTCOMES, SOURCES, Decision, ReadEvent, Record, Trace


def _require(event: dict, field: str, line_no: int) -> object:
    if field not in event:
        raise ValueError("line %d: missing field %r" % (line_no, field))
    return event[field]


def _as_int(value: object, field: str, line_no: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("line %d: field %r must be an integer" % (line_no, field))
    return value


def parse_event(event: dict, line_no: int) -> Record | ReadEvent | Decision:
    """Parse one decoded JSON object into a typed event."""
    kind = _require(event, "type", line_no)
    if kind == "write":
        source = _require(event, "source", line_no)
        if source not in SOURCES:
            raise ValueError(
                "line %d: unknown source %r (expected one of %s)"
                % (line_no, source, ", ".join(SOURCES))
            )
        supersedes = event.get("supersedes")
        if supersedes is not None and not isinstance(supersedes, str):
            raise ValueError("line %d: 'supersedes' must be a record id or null" % line_no)
        return Record(
            record_id=str(_require(event, "record_id", line_no)),
            key=str(_require(event, "key", line_no)),
            value=str(_require(event, "value", line_no)),
            source=str(source),
            t=_as_int(_require(event, "t", line_no), "t", line_no),
            supersedes=supersedes,
        )
    if kind == "read":
        return ReadEvent(
            decision_id=str(_require(event, "decision_id", line_no)),
            record_id=str(_require(event, "record_id", line_no)),
            rank=_as_int(_require(event, "rank", line_no), "rank", line_no),
            t=_as_int(_require(event, "t", line_no), "t", line_no),
        )
    if kind == "decision":
        outcome = _require(event, "outcome", line_no)
        if outcome not in OUTCOMES:
            raise ValueError(
                "line %d: unknown outcome %r (expected one of %s)"
                % (line_no, outcome, ", ".join(OUTCOMES))
            )
        chosen = event.get("chosen")
        correct = event.get("correct_value")
        if chosen is not None and not isinstance(chosen, str):
            raise ValueError("line %d: 'chosen' must be a string or null" % line_no)
        if correct is not None and not isinstance(correct, str):
            raise ValueError("line %d: 'correct_value' must be a string or null" % line_no)
        return Decision(
            decision_id=str(_require(event, "decision_id", line_no)),
            key=str(_require(event, "key", line_no)),
            chosen=chosen,
            correct_value=correct,
            outcome=str(outcome),
            t=_as_int(_require(event, "t", line_no), "t", line_no),
        )
    raise ValueError("line %d: unknown event type %r" % (line_no, kind))


def load_trace(path: str | Path) -> Trace:
    """Load a JSONL trace file. Raises ValueError on the first bad line."""
    trace = Trace()
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError("line %d: invalid JSON (%s)" % (line_no, exc)) from exc
            if not isinstance(event, dict):
                raise ValueError("line %d: each event must be a JSON object" % line_no)
            parsed = parse_event(event, line_no)
            if isinstance(parsed, Record):
                if parsed.record_id in trace.records:
                    raise ValueError(
                        "line %d: duplicate record_id %r" % (line_no, parsed.record_id)
                    )
                trace.records[parsed.record_id] = parsed
            elif isinstance(parsed, ReadEvent):
                trace.reads.append(parsed)
            else:
                if parsed.decision_id in trace.decisions:
                    raise ValueError(
                        "line %d: duplicate decision_id %r" % (line_no, parsed.decision_id)
                    )
                trace.decisions[parsed.decision_id] = parsed
    _check_references(trace)
    return trace


def _check_references(trace: Trace) -> None:
    """Reads must name records that exist; supersedes links must too."""
    for record in trace.records.values():
        if record.supersedes is not None and record.supersedes not in trace.records:
            raise ValueError(
                "record %r supersedes unknown record %r"
                % (record.record_id, record.supersedes)
            )
    for read in trace.reads:
        if read.record_id not in trace.records:
            raise ValueError(
                "read by decision %r names unknown record %r"
                % (read.decision_id, read.record_id)
            )


def trace_to_jsonl(trace: Trace) -> str:
    """Serialise a trace back to JSONL (writes, then reads, then decisions)."""
    lines: list[str] = []
    for record in sorted(trace.records.values(), key=lambda r: r.t):
        lines.append(
            json.dumps(
                {
                    "type": "write",
                    "record_id": record.record_id,
                    "key": record.key,
                    "value": record.value,
                    "source": record.source,
                    "t": record.t,
                    "supersedes": record.supersedes,
                }
            )
        )
    for read in sorted(trace.reads, key=lambda r: (r.t, r.decision_id, r.rank)):
        lines.append(
            json.dumps(
                {
                    "type": "read",
                    "decision_id": read.decision_id,
                    "record_id": read.record_id,
                    "rank": read.rank,
                    "t": read.t,
                }
            )
        )
    for decision in sorted(trace.decisions.values(), key=lambda d: d.t):
        lines.append(
            json.dumps(
                {
                    "type": "decision",
                    "decision_id": decision.decision_id,
                    "key": decision.key,
                    "chosen": decision.chosen,
                    "correct_value": decision.correct_value,
                    "outcome": decision.outcome,
                    "t": decision.t,
                }
            )
        )
    return "\n".join(lines) + ("\n" if lines else "")
