# Memory Autopsy

> When an agent makes a bad call, "the memory made me do it" is not a diagnosis. This tool opens the memory after the run and names the records: which one the decision acted on, which ones were stale, contradicted, superseded, poisoned — and which ones were never read at all.

**Author:** Amna Raheeba · Companion to my governed shared memory ([governed-shared-memory](https://github.com/Amna-Raheeba/governed-shared-memory)), which governs writes and access live; my luck audit ([luck-audit](https://github.com/Amna-Raheeba/luck-audit)), which audits whether successful runs were evidenced; and my clinical pre-mortem agent ([clinical-pre-mortem-agent](https://github.com/Amna-Raheeba/clinical-pre-mortem-agent)), which imagines failures before they happen. This one diagnoses memory-caused failures after the fact.

---

## 1. Overview

### 1.1 The problem

Agent memory systems are good at persistence and bad at truth-maintenance: a stored fact, true when written, can quietly become false, and the agent keeps acting on it with full confidence. When a run goes wrong, the operator's question is forensic — *which memory record caused this decision?* — and the usual answers are either a manual grep through the store or an LLM judge asked to guess. Neither is reproducible, and neither separates the failure modes: a record can be stale (read after it was superseded), contradicted (a live parallel version disagrees), superseded (replaced, never read again), poisoned (planted by an untrusted source), or simply unused. Those are different bugs with different fixes, and a tool that lumps them together cannot tell you which one you have.

### 1.2 The idea

A **deterministic, offline post-mortem for agent memory traces**. Feed it a JSONL trace of memory writes, reads and decisions, and it returns:

- a **blame graph**: every decision linked to the records it read, with the decisive (rank-1) record, the causal set from leave-one-out replay, and a redundant flag when no single removal flips the decision;
- a **per-record verdict** from a 10-label taxonomy — poisoned, stale, overruled, contradicted, helpful, misleading, bystander, unresolved, superseded, unused — with the reason attached;
- **aggregate rates**: stale-read rate, poison-influence rate, contradiction rate, redundant-decision rate.

The two mechanisms that make it more than a linter:

- **Versioned-provenance stale-read detection.** Supersession is explicit: a write names the record it replaces. A read is stale only when it happens after that superseding write. A read at the exact same tick raced the update and is not blamed.
- **Leave-one-out counterfactual replay.** Remove one record from a decision's read set and replay the decision rule. If the chosen value changes, the record was individually necessary. If nothing changes, the evidence was redundant — and the autopsy says so instead of naming a false single cause.

### 1.3 What it is not

- Not a memory store. It does not hold memories, rank retrievals, or decide what to keep. It reads a trace someone else produced.
- Not a live guardrail. It diagnoses after the run; blocking bad reads in real time is the guardrail middleware's job.
- Not an LLM judge. No model call, no embedding, no GPU. Stdlib-only, deterministic, fully offline — the same trace always produces the same autopsy.
- Not a policy checker. It does not know whether an action was allowed, only which memory records shaped it and what was wrong with them.

## 2. How It Works

### 2.1 The trace format

One JSONL event per line, on a logical clock `t` (an integer; wall-clock timestamps are never required):

```json
{"type": "write", "record_id": "r1", "key": "hotel", "value": "Hilton", "source": "agent", "t": 1, "supersedes": null}
{"type": "read", "decision_id": "d1", "record_id": "r1", "rank": 1, "t": 3}
{"type": "decision", "decision_id": "d1", "key": "hotel", "chosen": "Hilton", "correct_value": "Marriott", "outcome": "incorrect", "t": 5}
```

Sources are `user` | `agent` | `tool` | `untrusted`. Outcomes are `correct` | `incorrect` | `unknown` (`correct_value: null` for unlabelled decisions). A write with no `supersedes` link starts a **parallel version** — it does not implicitly supersede anything. That is the whole point: implicit overwriting is how contradictions get silently destroyed, and the autopsy needs them alive to diagnose them.

### 2.2 Verdicts

| Verdict | Meaning |
|---|---|
| `poisoned` | Untrusted source, and it either drove a wrong decision or contradicts a trusted record holding the current known truth |
| `stale` | Read after an explicit supersession (a stale read) |
| `overruled` | Held the correct value, was not the record acted on, and the decision went wrong anyway — good evidence ignored |
| `contradicted` | A live parallel version disagreed, and the agent saw both sides in the same decision |
| `helpful` | Decisive for a correct decision, or read for one holding the correct value |
| `misleading` | Decisive for an incorrect decision, with no staleness, contradiction or poison found |
| `bystander` | Read while a decision went wrong, but did not decide it |
| `unresolved` | Read (for its own key) only by decisions with unknown outcomes |
| `superseded` | Replaced, and never read after the replacement |
| `unused` | Never read at all |

Priority is first-match in the order above, and the order is part of the contract (tested): a record can be stale *and* contradicted, and the autopsy must pick one label. Two scoping rules keep the labels honest:

- **Contradictions are scoped to one decision.** A record is `contradicted` only when its conflicting partner was read by the *same* decision. A leftover conflict from an earlier episode does not make a later record contradicted — the store accumulates parallel versions across decisions, and the first version of this rule blamed later records for earlier episodes' conflicts (see `docs/experiment_log.md`).
- **Poison's structural clause needs the current truth.** An untrusted record is structurally poisoned only when it contradicts a trusted record holding the value the *latest* labelled decision confirms as correct. A value that was correct two episodes ago is not current truth.

### 2.3 Blame graph and replay

The decision rule the autopsy replays is the one the trace itself shows: the agent acted on the value of the highest-ranked record it read. On traces produced by that rule, leave-one-out replay is exact. On real LLM traces it is an approximation — the model may weigh records differently — and the verdicts that do not depend on the decision rule (stale reads, superseded, unused, structural poison) stay valid while causal claims weaken. See section 7.

### 2.4 Prior art — and what is different here

| Prior work | What it does | How this differs |
|---|---|---|
| **MemAudit** (arXiv 2605.23723, May 2026) | Post-hoc causal auditing of *poisoned* agent memory: LLM counterfactual influence + consistency graph; QA attack success 70% → 0% on GPT-4o | Closest concept. MemAudit is LLM-based and poison-only. This is offline, stdlib-only, deterministic replay with no model call, and covers the full failure taxonomy (10 verdicts), not just poison |
| **MEMOIR / TRACE** (arXiv 2611.07631) | Retrospective attribution of retrieved memories to answers (lexical + counterfactual), inside a memory lifecycle that updates retrieval priority | Attribution as a means to tune retrieval, not a post-mortem diagnosis; LLM-judged |
| **memory-autopsy-mcp** (Glama, Oct 2026) | MCP server; `memory_lint` scans a memory *store* for duplicates, contradictions and staleness | A static store lint. It cannot tell whether a stale record was actually *read*, which record drove which decision, or whether the evidence was redundant |
| **STALE benchmark** (May 2026) | 400 expert-validated conflict scenarios measuring stale-memory handling | A benchmark, not a diagnostic tool |
| **ctx** (ctxrs/ctx) | "Git blame for agent sessions" — traces committed code to the session that wrote it | Blames code to sessions, not decisions to memory records |
| **agent-architecture-audit** (skill) | Diagnostic checklist workflow for agent systems, incl. stale memory | A checklist, not a tool |

No prior tool combines all four: decision-to-record attribution on plain traces, versioned-provenance stale-*read* detection, a per-record blame taxonomy, and deterministic leave-one-out replay — with no model, no network, and no keys.

## 3. Measured Results

Evaluation: a seeded simulator generates 250 traces (50 per scenario — healthy, stale, poisoned, contradictory, mixed), 2,807 records, 2,401 reads, 1,350 decisions. Every record carries a ground-truth verdict assigned at construction, and every decision a ground-truth decisive record. Run `python scripts/reproduce_results.py` to regenerate every number below.

| Metric | Measured |
|---|---|
| Decisive-record recovery | **1.000** (1,350/1,350; 1.000 in every scenario) |
| Per-verdict precision / recall | **1.000 / 1.000** for all 9 classes with instances (`bystander`: no instances in this dataset) |
| Stale-read rate | **0.1249** (300/2,401 reads) |
| Poison-influence rate | **0.3179** (303/953 incorrect decisions driven by a poisoned record) |
| Contradiction rate | **0.2156** (291/1,350 decisions read a contradicted record) |
| Redundant-decision rate | **0.1163** (157/1,350 decisions no single removal flips) |

Seed sensitivity: the same perfect per-verdict scores on seeds 1, 42 and 123 (1,000 traces total). Read these numbers honestly: the rules are exact on synthetic traces because the simulator and the diagnoser share the trace contract (explicit supersession, rank-1 decision rule). The evaluation's real value is that it *caught two rule bugs during development* — cross-episode contradiction leakage (contradicted precision 0.60 before the same-decision scoping fix) and stale-truth poisoning (poisoned precision 0.94 before the latest-truth fix). See `docs/experiment_log.md`. The rates above are properties of the scenario mix, not of real agents.

Demo trace (`examples/demo_trace.jsonl`, a stale-memory incident plus a poisoned flight): stale-read rate 0.200, poison-influence rate 0.500; verdicts r1 stale, r4 poisoned, r2/r3 overruled, r5 helpful, r6 unused.

## 4. Quickstart

```bash
python -m memory_autopsy autopsy examples/demo_trace.jsonl
python -m memory_autopsy autopsy trace.jsonl --json report.json --markdown report.md
python -m memory_autopsy autopsy trace.jsonl --blame d1
python -m memory_autopsy blame-graph trace.jsonl --out graph.json
python -m memory_autopsy simulate --scenario stale --seed 7 --out stale.jsonl
```

Dashboard (needs Streamlit):

```bash
pip install -r requirements.txt
streamlit run dashboard/app.py
```

Tab 1 is the blame report (pick a scenario trace, see every verdict and attribution); tab 2 is the evaluation (headline numbers from `results/metrics.json`).

## 5. Autopsying Your Own Traces

1. Log three event kinds in JSONL: `write` (record_id, key, value, source, t, supersedes), `read` (decision_id, record_id, rank, t), `decision` (decision_id, key, chosen, correct_value, outcome, t).
2. Link supersession explicitly: when a write replaces a record, set `supersedes` to the old record's id. A write with no link is a parallel version — if your writer never links, everything will read as contradictions, and the autopsy will tell you so.
3. Label outcomes where you can. Without `correct_value`, the poison structural clause cannot fire and `overruled`/`helpful`/`misleading` degrade to `unresolved` — the stale/superseded/unused verdicts still work, because they only need the clock and the read log.
4. Keep the decision rule in mind: the replay assumes the agent acted on its rank-1 read. If your agent merges records or re-ranks them with a model, treat `causal_records` as an approximation and lean on the verdicts.

## 6. Repository Map

```
memory_autopsy/        core package (stdlib only)
  models.py            Record / ReadEvent / Decision / Trace
  trace.py             JSONL loader + validator (fails loudly, never skips)
  store.py             versioned store: supersession, liveness, contradictions
  attribution.py       blame graph + leave-one-out replay
  diagnosis.py         the 10-verdict diagnosis, priority order
  report.py            aggregate rates + Markdown/JSON reports
  simulate.py          seeded trace generator with ground truth
  evaluate.py          per-verdict precision/recall scoring
  __main__.py          CLI: autopsy / simulate / blame-graph
dashboard/             Streamlit app (2 tabs) + helpers
examples/              demo_trace.jsonl + autopsy_a_trace.py
notebooks/             01_demo_run.py, 02_evaluation_experiment.py
scripts/               reproduce_results.py (regenerates results/, fails on drift)
tests/                 75 tests, plain pytest
results/               metrics.json, evaluation.csv, summary.md
docs/                  api.md, architecture.md, experiment_log.md, metrics.md
```

## 7. Limitations

- **Replay is exact only under the rank-1 rule.** On real LLM traces the model may combine, re-weight or ignore records; then `causal_records` is an approximation. The clock-based verdicts (stale, superseded, unused) and the structural poison clause do not depend on the rule.
- **The 1.000 scores are contract checks, not real-world accuracy.** They prove the implementation matches its trace contract on 1,000 synthetic traces. Nothing here has been run against a real agent's memory yet.
- **Contradiction detection is lexical.** Two records contradict when their values differ as strings. Paraphrased contradictions are missed — no embeddings by design (offline, stdlib-only).
- **Structural poison needs labels.** Without a labelled decision confirming the current truth for a key, an unread untrusted record cannot be flagged structurally; only the drove-a-wrong-decision clause fires.
- **One verdict per record.** Priority order resolves overlaps, which means a record that is both stale and poisoned is reported as poisoned and its staleness is visible only in the read log. The blame graph keeps both edges.
- **The simulator is small.** Five keys, five decisions per trace, one failure mode per decision. The aggregate rates describe the scenario mix, not any real agent.
