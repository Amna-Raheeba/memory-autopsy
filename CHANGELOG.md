# Changelog

## 0.1.0 — 2026-11-17

- **New project.** Post-mortem diagnosis of an agent's memory system from a JSONL trace of writes, reads and decisions.
- **Blame graph + leave-one-out replay** (`memory_autopsy/attribution.py`): every decision linked to the records it read, with the decisive (rank-1) record, the causal set from exact replay, and a redundant flag when no single removal flips the decision. Redundant decisions measured at 11.6% (157/1,350) on the seeded dataset — the tool reports redundancy instead of naming a false single cause.
- **10-verdict per-record diagnosis** (`memory_autopsy/diagnosis.py`): poisoned, stale, overruled, contradicted, helpful, misleading, bystander, unresolved, superseded, unused, in a tested priority order.
- **Versioned-provenance stale-read detection** (`memory_autopsy/store.py`): supersession is explicit; a read is stale only after the superseding write, and a read at the exact same tick is not blamed.
- **Seeded simulator with ground truth** (`memory_autopsy/simulate.py`): 5 scenarios (healthy, stale, poisoned, contradictory, mixed) plus edge cases (untrusted-but-correct record, never-read record, unknown-outcome decision). 250 traces, 2,807 records, 2,401 reads, 1,350 decisions.
- **Evaluation** (`memory_autopsy/evaluate.py`, `scripts/reproduce_results.py`): decisive-record recovery 1.000 (1,350/1,350); per-verdict precision/recall 1.000 for all 9 classes with instances; stale-read rate 0.1249, poison-influence rate 0.3179, contradiction rate 0.2156. Same perfect scores on seeds 1, 42, 123.
- **Two rule bugs found and fixed during evaluation** (see `docs/experiment_log.md`): contradiction verdicts leaked across episodes (precision 0.60 before the same-decision scoping fix); the poison structural clause used any past correct value instead of the latest (precision 0.94 before the fix).
- **Dashboard** (`dashboard/app.py`): blame-report tab + evaluation tab, Streamlit AppTest with 0 exceptions.
- 75 tests, plain `pytest`, Python 3.10/3.11/3.12 compatible (no multi-line f-strings).
