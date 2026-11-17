# Metrics

All metrics are plain fractions over a trace (or over the seeded
dataset), never model scores. Regenerate with
`python scripts/reproduce_results.py` (seed 7, 250 traces: 50 per
scenario, 2,807 records, 2,401 reads, 1,350 decisions).

## Per-verdict precision / recall

Scored against the simulator's construction labels. A class with no
instances on either side reports `None`, not 1.0.

| Verdict | Precision | Recall | tp | fp | fn |
|---|---|---|---|---|---|
| poisoned | 1.000 | 1.000 | 303 | 0 | 0 |
| stale | 1.000 | 1.000 | 300 | 0 | 0 |
| overruled | 1.000 | 1.000 | 894 | 0 | 0 |
| contradicted | 1.000 | 1.000 | 291 | 0 | 0 |
| helpful | 1.000 | 1.000 | 504 | 0 | 0 |
| misleading | 1.000 | 1.000 | 59 | 0 | 0 |
| bystander | n/a | n/a | 0 | 0 | 0 |
| unresolved | 1.000 | 1.000 | 50 | 0 | 0 |
| superseded | 1.000 | 1.000 | 356 | 0 | 0 |
| unused | 1.000 | 1.000 | 50 | 0 | 0 |

`bystander` has no instances in this dataset: the simulator never
reads a wrong-valued record at rank ≥ 2 for a wrong decision. The
verdict is covered by hand-built traces in `tests/test_diagnosis.py`.

## Attribution

- **Decisive-record recovery: 1.000 (1,350/1,350)**, 1.000 in every
  scenario. The rank-1 record is observed in the trace, so this
  validates the attribution plumbing, not a guess.

## Aggregate rates (dataset-wide)

| Rate | Value | Numerator / denominator |
|---|---|---|
| stale-read rate | 0.1249 | 300 / 2,401 reads |
| poison-influence rate | 0.3179 | 303 / 953 incorrect decisions |
| contradiction rate | 0.2156 | 291 / 1,350 decisions |
| redundant-decision rate | 0.1163 | 157 / 1,350 decisions with reads |

These rates are properties of the scenario mix (deliberately
failure-heavy: 4 of 5 scenarios inject a failure mode), not of any
real agent. A healthy-only run scores 0.000 on all four.

## Seed sensitivity

Seeds 1, 42, 123 (250 traces each): decisive recovery 1.000 and no
imperfect verdict class on any seed.
