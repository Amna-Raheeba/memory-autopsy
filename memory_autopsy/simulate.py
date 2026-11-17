"""Seeded synthetic traces with known ground truth.

The simulator plays a small agent that answers key queries ("which
hotel?", "which flight?") from its memory. Each scenario injects one
memory failure mode by construction, so the intended verdict of every
record and the decisive record of every decision are KNOWN — the
autopsy is scored against them, not against a human label.

Scenarios:

- ``healthy`` — the world changes, the agent writes the new true
  value (superseding the old), reads the newest record. All decisions
  correct. One parallel duplicate (same value, no supersedes link)
  makes some decisions redundant-evidence cases.
- ``stale`` — the world changes and the new record supersedes the
  old, but retrieval still returns the old record first (cache lag).
  The decision is wrong; the old record is read after supersession.
- ``poisoned`` — an untrusted record with a wrong value is retrieved
  first. The decision is wrong.
- ``contradictory`` — a wrong-value record is written WITHOUT a
  supersedes link, so it lives in parallel with the true record and
  both are read. The decision follows the wrong one.
- ``mixed`` — per decision, a seeded pick of the four modes plus
  ``misleading`` (a plain wrong trusted record that does supersede
  the old one: no staleness, no contradiction, just a bad write),
  plus edge cases: an untrusted-but-correct record (must NOT be
  called poisoned), a superseded record never read again, a record
  never read at all, and one decision with an unknown outcome.

The agent's decision rule — act on the value of the highest-ranked
record read — is the same rule the autopsy replays, so replay is
exact on these traces. On real LLM traces the rule is an
approximation; see README section 7.
"""

from __future__ import annotations

import random

from memory_autopsy.models import Decision, ReadEvent, Record, Trace

SCENARIOS = ("healthy", "stale", "poisoned", "contradictory", "mixed")

# Plausible values per key; the "world" picks one, wrong values are
# the other entries in the pool.
VALUE_POOLS = {
    "hotel": ["Hilton", "Marriott", "Hyatt", "Sheraton"],
    "flight": ["PK701", "PK702", "PK703", "PK704"],
    "restaurant": ["Lahore Tikka", "Salt n Pepper", "Bundu Khan", "Butt Karahi"],
    "doctor": ["Dr. Ayesha", "Dr. Bilal", "Dr. Sana", "Dr. Omar"],
    "city": ["Faisalabad", "Lahore", "Islamabad", "Karachi"],
}
KEYS = list(VALUE_POOLS)


class _Builder:
    """Builds one trace event by event on a logical clock."""

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.trace = Trace()
        self.truth_verdicts: dict[str, str] = {}
        self.truth_decisive: dict[str, str | None] = {}
        self.t = 0
        self.counter = 0
        self.world: dict[str, str] = {
            key: self.rng.choice(values) for key, values in VALUE_POOLS.items()
        }

    def _next_id(self, prefix: str) -> str:
        self.counter += 1
        return "%s%d" % (prefix, self.counter)

    def _tick(self) -> int:
        self.t += 1
        return self.t

    def write(
        self,
        key: str,
        value: str,
        source: str = "agent",
        supersedes: str | None = None,
        intended: str | None = None,
    ) -> str:
        record_id = self._next_id("r")
        record = Record(
            record_id=record_id,
            key=key,
            value=value,
            source=source,
            t=self._tick(),
            supersedes=supersedes,
        )
        self.trace.records[record_id] = record
        if intended is not None:
            self.truth_verdicts[record_id] = intended
        return record_id

    def decide(
        self,
        key: str,
        read_ids: list[str],
        correct_value: str | None = None,
        outcome: str | None = None,
    ) -> str:
        """A decision that acts on the rank-1 read record's value."""
        decision_id = self._next_id("d")
        chosen = None
        if read_ids:
            chosen = self.trace.records[read_ids[0]].value
        if outcome is None:
            if correct_value is None:
                outcome = "unknown"
            else:
                outcome = "correct" if chosen == correct_value else "incorrect"
        decision = Decision(
            decision_id=decision_id,
            key=key,
            chosen=chosen,
            correct_value=correct_value,
            outcome=outcome,
            t=self._tick(),
        )
        self.trace.decisions[decision_id] = decision
        for rank, record_id in enumerate(read_ids, start=1):
            self.trace.reads.append(
                ReadEvent(
                    decision_id=decision_id,
                    record_id=record_id,
                    rank=rank,
                    t=self._tick(),
                )
            )
        self.truth_decisive[decision_id] = read_ids[0] if read_ids else None
        return decision_id

    def _wrong_value(self, key: str, true_value: str) -> str:
        pool = [v for v in VALUE_POOLS[key] if v != true_value]
        return self.rng.choice(pool)

    def _update_world(self, key: str) -> str:
        new_value = self._wrong_value(key, self.world[key])
        self.world[key] = new_value
        return new_value

    def truth(self) -> dict:
        return {
            "verdicts": dict(self.truth_verdicts),
            "decisive": dict(self.truth_decisive),
        }


def _healthy(builder: _Builder, key: str) -> None:
    """World changes; agent writes and reads the new true value."""
    old_value = builder.world[key]
    old_id = builder.write(key, old_value, source="agent", intended="superseded")
    new_value = builder._update_world(key)
    new_id = builder.write(
        key, new_value, source="agent", supersedes=old_id, intended="helpful"
    )
    if builder.rng.random() < 0.5:
        # Parallel duplicate with the same value: removing the
        # decisive record does not flip the decision (redundant).
        dup_id = builder.write(key, new_value, source="user", intended="helpful")
        builder.decide(key, [new_id, dup_id], correct_value=new_value)
    else:
        builder.decide(key, [new_id], correct_value=new_value)


def _stale(builder: _Builder, key: str) -> None:
    """World changes, new record supersedes old, retrieval lags."""
    old_value = builder.world[key]
    old_id = builder.write(key, old_value, source="agent", intended="stale")
    new_value = builder._update_world(key)
    new_id = builder.write(
        key, new_value, source="agent", supersedes=old_id, intended="overruled"
    )
    builder.decide(key, [old_id, new_id], correct_value=new_value)


def _poisoned(builder: _Builder, key: str) -> None:
    """An untrusted wrong-value record is retrieved first."""
    true_value = builder.world[key]
    true_id = builder.write(key, true_value, source="tool", intended="overruled")
    poison_value = builder._wrong_value(key, true_value)
    poison_id = builder.write(
        key, poison_value, source="untrusted", intended="poisoned"
    )
    builder.decide(key, [poison_id, true_id], correct_value=true_value)


def _contradictory(builder: _Builder, key: str) -> None:
    """A wrong record is written WITHOUT a supersedes link."""
    true_value = builder.world[key]
    true_id = builder.write(key, true_value, source="agent", intended="overruled")
    wrong_value = builder._wrong_value(key, true_value)
    wrong_id = builder.write(
        key, wrong_value, source="agent", intended="contradicted"
    )
    builder.decide(key, [wrong_id, true_id], correct_value=true_value)


def _misleading(builder: _Builder, key: str) -> None:
    """A plain bad trusted write that does supersede the old record."""
    old_value = builder.world[key]
    old_id = builder.write(key, old_value, source="agent", intended="superseded")
    wrong_value = builder._wrong_value(key, old_value)
    wrong_id = builder.write(
        key, wrong_value, source="agent", supersedes=old_id, intended="misleading"
    )
    builder.decide(key, [wrong_id], correct_value=old_value)


def _edge_cases(builder: _Builder) -> None:
    """Records that test the verdict boundaries, in one mixed trace."""
    key = builder.rng.choice(KEYS)
    true_value = builder.world[key]
    # Untrusted but correct and decisive for a correct decision: must
    # be helpful, not poisoned.
    good_id = builder.write(
        key, true_value, source="untrusted", intended="helpful"
    )
    builder.decide(key, [good_id], correct_value=true_value)
    # A record never read at all.
    builder.write(key, true_value, source="agent", intended="unused")
    # A decision with an unknown outcome, reading its own record.
    key2 = builder.rng.choice([k for k in KEYS if k != key])
    unknown_id = builder.write(
        key2, builder.world[key2], source="agent", intended="unresolved"
    )
    builder.decide(key2, [unknown_id], correct_value=None, outcome="unknown")


_MODES = {
    "healthy": _healthy,
    "stale": _stale,
    "poisoned": _poisoned,
    "contradictory": _contradictory,
    "misleading": _misleading,
}


def generate_trace(
    scenario: str, seed: int, n_decisions: int = 5
) -> tuple[Trace, dict]:
    """Generate one seeded trace and its ground-truth labels."""
    if scenario not in SCENARIOS:
        raise ValueError("unknown scenario %r (expected one of %s)" % (scenario, ", ".join(SCENARIOS)))
    builder = _Builder(seed)
    if scenario == "mixed":
        modes = ["healthy", "stale", "poisoned", "contradictory", "misleading"]
        for i in range(n_decisions):
            key = builder.rng.choice(KEYS)
            _MODES[builder.rng.choice(modes)](builder, key)
        _edge_cases(builder)
    else:
        for _ in range(n_decisions):
            key = builder.rng.choice(KEYS)
            _MODES[scenario](builder, key)
    return builder.trace, builder.truth()


def generate_dataset(
    seed: int = 7, per_scenario: int = 50, n_decisions: int = 5
) -> list[tuple[str, Trace, dict]]:
    """The headline dataset: per_scenario traces per scenario."""
    dataset: list[tuple[str, Trace, dict]] = []
    for scenario in SCENARIOS:
        for i in range(per_scenario):
            trace, truth = generate_trace(scenario, seed * 1000 + i, n_decisions)
            dataset.append((scenario, trace, truth))
    return dataset
