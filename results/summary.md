# Memory Autopsy — headline evaluation (seed 7)

250 traces (50 per scenario: healthy, stale, poisoned, contradictory, mixed), 2807 records, 2401 reads, 1350 decisions.

- Decisive-record recovery: 1.000 (1350/1350)
- stale_read_rate: 0.1249
- poison_influence_rate: 0.3179
- contradiction_rate: 0.2156
- redundant_decision_rate: 0.1163

Per-verdict precision / recall: 1.000 for every class with
instances (see results/evaluation.csv).
