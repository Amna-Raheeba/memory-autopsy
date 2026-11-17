# API

All public entry points. Everything is stdlib-only; `streamlit` is
needed only for `dashboard/app.py`.

## Loading a trace

```python
from memory_autopsy.trace import load_trace, trace_to_jsonl

trace = load_trace("trace.jsonl")   # raises ValueError on the first bad line
text = trace_to_jsonl(trace)        # round-trip serialisation
```

`Trace` holds `records: dict[str, Record]`, `reads: list[ReadEvent]`,
`decisions: dict[str, Decision]`, plus helpers `reads_for(decision_id)`,
`records_for_key(key)`, `decisions_for_key(key)`.

## Running an autopsy

```python
from memory_autopsy.diagnosis import diagnose_trace, diagnose_record
from memory_autopsy.report import aggregate, markdown_report, json_report
from memory_autopsy.store import VersionedStore

autopsy = diagnose_trace(trace)
# autopsy["verdicts"][record_id] -> {"record_id", "verdict", "reason"}
# autopsy["attributions"][decision_id] -> decisive/causal/redundant
# autopsy["stale_reads"] -> int
metrics = aggregate(trace, autopsy)
print(markdown_report(trace, autopsy))
```

## Attribution

```python
from memory_autopsy.attribution import (
    blame_graph, replay_decision, influence, causal_set,
    is_redundant, decisive_record, attribute_decision,
)

replay_decision(trace, decision, frozenset({"r1"}))  # value without r1, or None
influence(trace, decision, "r1")                     # does removing r1 flip it?
graph = blame_graph(trace)  # {"nodes": [...], "edges": [...]} — JSON-serialisable
```

## Simulation and scoring

```python
from memory_autopsy.simulate import generate_trace, generate_dataset
from memory_autopsy.evaluate import score_trace, score_dataset

trace, truth = generate_trace("mixed", seed=7, n_decisions=5)
dataset = generate_dataset(seed=7, per_scenario=50, n_decisions=5)
score = score_trace(trace, truth)   # per-verdict P/R, decisive recovery
```

`score_trace` returns `None` (not 1.0) for precision/recall of a
verdict class with no instances on either side.

## CLI

```
memory-autopsy autopsy TRACE [--json OUT] [--markdown OUT] [--blame DECISION]
memory-autopsy simulate [--scenario NAME] [--seed N] [--per-scenario N]
                        [--n-decisions N] --out FILE
memory-autopsy blame-graph TRACE [--out FILE]
```

Exit code 2 for an unknown decision id or scenario; 0 otherwise.
