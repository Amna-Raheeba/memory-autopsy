# Architecture

## The trace contract

A trace is a JSONL file of three event kinds on a logical clock `t`.
The loader fails loudly on the first bad line (bad JSON, unknown
type/source/outcome, missing field, duplicate id, dangling read or
supersedes reference) — an autopsy that silently drops events would
blame the wrong records.

The two load-bearing design decisions:

1. **Supersession is explicit.** Only a write naming a record in
   `supersedes` replaces it. A same-key write with no link is a
   parallel version. Implicit overwriting would destroy the very
   contradictions the autopsy exists to find.
2. **The decision rule is rank-1.** The agent acted on the value of
   the highest-ranked record it read. This is an observed fact of
   the trace format, not a model of a model — and it is what makes
   leave-one-out replay exact instead of estimated.

## Pipeline

```
JSONL trace
  -> trace.py        parse + validate
  -> store.py        versioned store: supersession chains, liveness,
                     contradiction pairs, trusted-truth lookup
  -> attribution.py  blame graph, replay, influence, causal sets
  -> diagnosis.py    one verdict per record (priority order)
  -> report.py       aggregate rates, Markdown/JSON reports
```

`diagnosis.py` is the only module that assigns meaning; everything
below it is facts about the trace (what was superseded when, what
was read together). That split is what makes the verdict rules
testable in isolation: 17 of the 75 tests build hand-made traces
and assert one verdict each.

## Verdict priority

First match wins: poisoned, stale, overruled, contradicted, helpful,
misleading, bystander, unresolved, superseded, unused. The order
encodes two judgements: poison outranks everything (a planted
record is the finding even when it is also stale), and overruled
outranks contradicted (good evidence ignored is a sharper diagnosis
than merely participating in a conflict).

## The simulator

`simulate.py` plays a small agent that answers key queries from its
memory. Each scenario injects one failure mode by construction, so
every record's intended verdict and every decision's decisive record
are known. The simulator and the diagnoser share only the trace
contract — the simulator never calls the diagnoser — so agreement
between them is a genuine check, not a tautology. (It is still a
check against synthetic data; see README section 7.)
