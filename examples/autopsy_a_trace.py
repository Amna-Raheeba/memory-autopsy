"""Autopsy the bundled demo trace and print the report.

Run from the repo root:

    python examples/autopsy_a_trace.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.helpers import demo_autopsy
from memory_autopsy.report import markdown_report

if __name__ == "__main__":
    trace, autopsy, _metrics = demo_autopsy()
    print(markdown_report(trace, autopsy))
    print("Demo trace: %s" % (ROOT / "examples" / "demo_trace.jsonl"))
