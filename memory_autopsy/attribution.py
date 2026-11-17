"""Attribution: which records shaped which decisions.

The decision function this autopsy replays is the one the trace
itself shows: the agent acted on the value of the highest-ranked
(rank 1) record it read for the decision's key. That is an observed
fact of the trace, not a model guess — so leave-one-out replay is
EXACT on traces produced by that rule, and the replay is honest
about its limit on real LLM traces (see README section 7).

Two outputs:

- the **blame graph**: decision -> record edges (with rank and
  whether the record was causal), and record -> record edges
  (``supersedes`` / ``contradicts``). A decision's blame is the set
  of records it read; its cause is the rank-1 record.
- **leave-one-out influence**: remove one record from a decision's
  read set and replay. If the chosen value changes, the record was
  individually necessary. If NO removal changes the outcome, the
  decision's evidence was redundant — the autopsy says so instead of
  naming a false single cause.
"""

from __future__ import annotations

from memory_autopsy.models import Decision, Trace


def replay_decision(trace: Trace, decision: Decision, removed: frozenset[str]) -> str | None:
    """Re-run a decision's read set with some records removed.

    Returns the value the agent would have acted on: the value of the
    lowest-rank read record not in ``removed``, or None when nothing
    is left to read (the agent would have had no memory to act on).
    """
    for read in trace.reads_for(decision.decision_id):
        if read.record_id not in removed:
            return trace.records[read.record_id].value
    return None


def decisive_record(trace: Trace, decision: Decision) -> str | None:
    """The rank-1 record a decision acted on, or None if it read nothing."""
    reads = trace.reads_for(decision.decision_id)
    if not reads:
        return None
    return reads[0].record_id


def influence(trace: Trace, decision: Decision, record_id: str) -> bool:
    """Was this record individually necessary for the decision?

    True when removing it (and only it) changes the chosen value.
    A record can be decisive (rank 1) yet not influential: if the
    rank-2 record holds the same value, the decision survives the
    removal — redundant evidence, not a single cause.
    """
    original = decision.chosen
    replayed = replay_decision(trace, decision, frozenset({record_id}))
    return replayed != original


def causal_set(trace: Trace, decision: Decision) -> list[str]:
    """Records whose individual removal flips this decision."""
    return [
        read.record_id
        for read in trace.reads_for(decision.decision_id)
        if influence(trace, decision, read.record_id)
    ]


def is_redundant(trace: Trace, decision: Decision) -> bool:
    """True when the decision read records but no single removal flips it."""
    reads = trace.reads_for(decision.decision_id)
    return bool(reads) and not causal_set(trace, decision)


def attribute_decision(trace: Trace, decision: Decision) -> dict:
    """Full attribution for one decision."""
    reads = trace.reads_for(decision.decision_id)
    causal = causal_set(trace, decision)
    return {
        "decision_id": decision.decision_id,
        "key": decision.key,
        "chosen": decision.chosen,
        "outcome": decision.outcome,
        "decisive_record": decisive_record(trace, decision),
        "read_records": [r.record_id for r in reads],
        "causal_records": causal,
        "redundant": is_redundant(trace, decision),
        "read_count": len(reads),
    }


def blame_graph(trace: Trace) -> dict:
    """The blame graph as plain data (JSON-serialisable).

    Nodes: every decision and every record. Edges:
    - decision -> record, labelled ``read`` with rank, ``causal``
      when leave-one-out flips the decision;
    - record -> record, labelled ``supersedes`` or ``contradicts``.
    """
    nodes = [{"id": d.decision_id, "kind": "decision", "key": d.key} for d in trace.decisions.values()]
    nodes += [
        {"id": r.record_id, "kind": "record", "key": r.key, "source": r.source}
        for r in trace.records.values()
    ]
    edges: list[dict] = []
    for decision in trace.decisions.values():
        attribution = attribute_decision(trace, decision)
        for read in trace.reads_for(decision.decision_id):
            edges.append(
                {
                    "from": decision.decision_id,
                    "to": read.record_id,
                    "kind": "read",
                    "rank": read.rank,
                    "causal": read.record_id in attribution["causal_records"],
                }
            )
    for record in trace.records.values():
        if record.supersedes is not None:
            edges.append(
                {
                    "from": record.record_id,
                    "to": record.supersedes,
                    "kind": "supersedes",
                }
            )
    from memory_autopsy.store import VersionedStore

    store = VersionedStore(trace)
    seen: set[tuple[str, str]] = set()
    for decision in trace.decisions.values():
        for first, second in store.contradiction_pairs(decision.key, decision.t):
            key = tuple(sorted((first.record_id, second.record_id)))
            if key not in seen:
                seen.add(key)
                edges.append(
                    {"from": first.record_id, "to": second.record_id, "kind": "contradicts"}
                )
    return {"nodes": nodes, "edges": edges}
