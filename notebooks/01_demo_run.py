"""Notebook 01 — demo run: autopsy the bundled stale-memory incident.

Run from the repo root:

    python notebooks/01_demo_run.py

Prints the Markdown report for examples/demo_trace.jsonl and the
blame graph summary (nodes, edges, and the causal record of each
decision). Expected: r1 stale, r4 poisoned, r2/r3 overruled,
r5 helpful, r6 unused; stale-read rate 0.200, poison-influence
rate 0.500.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.helpers import demo_autopsy  # noqa: E402
from memory_autopsy.attribution import blame_graph  # noqa: E402
from memory_autopsy.report import markdown_report  # noqa: E402


def main() -> None:
    trace, autopsy, _metrics = demo_autopsy()
    print(markdown_report(trace, autopsy))
    graph = blame_graph(trace)
    print("Blame graph: %d nodes, %d edges" % (len(graph["nodes"]), len(graph["edges"])))
    for decision_id, attribution in sorted(autopsy["attributions"].items()):
        print(
            "  %s: decisive=%s causal=%s redundant=%s"
            % (
                decision_id,
                attribution["decisive_record"],
                ",".join(attribution["causal_records"]) or "-",
                attribution["redundant"],
            )
        )


if __name__ == "__main__":
    main()
