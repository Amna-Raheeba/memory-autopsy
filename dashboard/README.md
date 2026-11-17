# Memory Autopsy — dashboard

Run from the repo root:

```bash
pip install -r requirements.txt
streamlit run dashboard/app.py
```

## Tabs

1. **Blame report** — pick a trace (the bundled demo incident, or one
   generated trace per scenario) and see every record's verdict with
   its reason, plus every decision's attribution (decisive record,
   causal set, redundant flag).
2. **Evaluation** — the headline numbers from `results/metrics.json`
   (per-verdict precision/recall over the 250-trace seeded dataset,
   decisive recovery by scenario). Run
   `python scripts/reproduce_results.py` first if the file is missing.

## Helpers

`dashboard/helpers.py` holds the Streamlit-free logic (load the demo
trace, build the verdict/decision tables, generate one trace per
scenario) so it stays unit-testable without the dashboard.
