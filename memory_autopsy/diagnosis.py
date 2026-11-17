"""Diagnosis: one verdict per record, with the reason attached.

Verdicts, in priority order (first match wins — a record can be
stale AND contradicted, and the autopsy must pick one label, so the
order is part of the contract and is tested):

1. ``poisoned``    — untrusted source AND (causal for an incorrect
   decision, or contradicts a trusted record on the same key).
2. ``stale``       — read after an explicit supersession (a stale read).
3. ``overruled``   — read, held the correct value, was not the record
   acted on, and the decision went WRONG anyway: good evidence the
   agent ignored. (Only for incorrect decisions: a correct decision
   that read agreeing records is support, not overruling.)
4. ``contradicted``— a live parallel version disagreed AND the agent
   saw both sides in the same decision. A leftover conflict from an
   earlier episode does not make a record contradicted.
5. ``helpful``     — decisive for a correct decision, or read for a
   correct decision holding the correct value.
6. ``misleading``  — decisive (rank 1) for an incorrect decision,
   not poisoned / stale / contradicted.
7. ``bystander``   — read, did not decide the outcome, held the wrong
   value while the decision went wrong anyway.
8. ``unresolved``  — read only by decisions whose outcome is unknown.
9. ``superseded``  — superseded and never read after the supersession.
10. ``unused``     — never read at all.

A record that is superseded but was read BEFORE the supersession is
``superseded``, not ``stale`` — the read was legitimate at the time.
"""

from __future__ import annotations

from memory_autopsy.attribution import decisive_record
from memory_autopsy.models import Trace
from memory_autopsy.store import VersionedStore

VERDICTS = (
    "poisoned",
    "stale",
    "overruled",
    "contradicted",
    "helpful",
    "misleading",
    "bystander",
    "unresolved",
    "superseded",
    "unused",
)


def diagnose_record(trace: Trace, store: VersionedStore, record_id: str) -> dict:
    """Verdict + reason for one record."""
    record = trace.records[record_id]
    reads = [r for r in trace.reads if r.record_id == record_id]
    # Outcome-based verdicts only make sense for decisions about this
    # record's own key; a read by a decision on another key is not
    # evidence about the record's value.
    decisions = [
        trace.decisions[r.decision_id]
        for r in reads
        if trace.decisions[r.decision_id].key == record.key
    ]
    known = [d for d in decisions if d.outcome != "unknown"]

    # 1. Poisoned: untrusted, and it either drove a wrong decision or
    #    structurally contradicts a trusted record on the same key.
    if record.source == "untrusted":
        drove_wrong = any(
            decisive_record(trace, d) == record_id and d.outcome == "incorrect"
            for d in decisions
        )
        if drove_wrong or store.contradicts_trusted(record_id) is not None:
            reason = "untrusted source"
            if drove_wrong:
                reason += "; decisive for an incorrect decision"
            if store.contradicts_trusted(record_id) is not None:
                reason += "; contradicts trusted record %s" % store.contradicts_trusted(record_id).record_id
            return {"record_id": record_id, "verdict": "poisoned", "reason": reason}

    # 2. Stale: read after an explicit supersession.
    stale_reads = [r for r in reads if store.is_stale_read(record_id, r.t)]
    if stale_reads:
        superseder = store.superseding_write(record_id)
        return {
            "record_id": record_id,
            "verdict": "stale",
            "reason": "read at t=%d after superseded by %s at t=%d"
            % (stale_reads[0].t, superseder.record_id, superseder.t),
        }

    # 3. Overruled: held the right value, was not acted on, and the
    #    decision went wrong anyway — good evidence ignored.
    if any(
        decisive_record(trace, d) != record_id
        and d.correct_value is not None
        and record.value == d.correct_value
        and d.outcome == "incorrect"
        for d in known
    ):
        return {
            "record_id": record_id,
            "verdict": "overruled",
            "reason": "held the correct value but was not the record acted on",
        }

    # 4. Contradicted: a live parallel version disagreed AND the agent
    #    saw both sides in the same decision. A leftover conflict from
    #    an earlier episode does not make this record contradicted.
    if any(
        store.contradiction_partners(
            record_id, d.t, set(trace.record_ids_read(d.decision_id))
        )
        for d in decisions
    ):
        return {
            "record_id": record_id,
            "verdict": "contradicted",
            "reason": "a live parallel version of %r held a different value in the same decision" % record.key,
        }

    # 5. Helpful: decisive for a correct decision, or read for one
    #    holding the correct value.
    if any(
        (decisive_record(trace, d) == record_id or record.value == d.correct_value)
        and d.outcome == "correct"
        for d in known
    ):
        return {
            "record_id": record_id,
            "verdict": "helpful",
            "reason": "supported a correct decision",
        }

    # 6. Misleading: decisive for an incorrect decision.
    if any(decisive_record(trace, d) == record_id and d.outcome == "incorrect" for d in known):
        return {
            "record_id": record_id,
            "verdict": "misleading",
            "reason": "decisive for an incorrect decision; no staleness, contradiction or poison found",
        }

    # 7. Bystander: read, wrong value, decision wrong anyway, not decisive.
    if any(d.outcome == "incorrect" for d in known):
        return {
            "record_id": record_id,
            "verdict": "bystander",
            "reason": "read while a decision went wrong, but did not decide it",
        }

    # 8. Unresolved: read (for its own key) only by decisions with
    #    unknown outcomes. A read by a decision on another key does
    #    not count — it says nothing about this record's value.
    if decisions and not known:
        return {
            "record_id": record_id,
            "verdict": "unresolved",
            "reason": "read only by decisions with unknown outcomes",
        }

    # 9. Superseded: replaced, and never read after the replacement.
    if store.superseding_write(record_id) is not None:
        superseder = store.superseding_write(record_id)
        return {
            "record_id": record_id,
            "verdict": "superseded",
            "reason": "superseded by %s at t=%d; never read after" % (superseder.record_id, superseder.t),
        }

    # 10. Unused.
    return {
        "record_id": record_id,
        "verdict": "unused",
        "reason": "never read by any decision",
    }


def diagnose_trace(trace: Trace) -> dict:
    """Full autopsy: per-record verdicts, per-decision attribution, metrics.

    Returns a JSON-serialisable report dict. Aggregate rates are
    computed in :mod:`memory_autopsy.report`.
    """
    from memory_autopsy.attribution import attribute_decision

    store = VersionedStore(trace)
    verdicts = {rid: diagnose_record(trace, store, rid) for rid in trace.records}
    attributions = {
        did: attribute_decision(trace, decision)
        for did, decision in trace.decisions.items()
    }
    stale_reads = sum(
        1 for read in trace.reads if store.is_stale_read(read.record_id, read.t)
    )
    return {
        "records": len(trace.records),
        "reads": len(trace.reads),
        "decisions": len(trace.decisions),
        "stale_reads": stale_reads,
        "verdicts": verdicts,
        "attributions": attributions,
    }
