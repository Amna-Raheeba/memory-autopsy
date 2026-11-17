"""Tests for the command line interface."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from memory_autopsy.__main__ import main

ROOT = Path(__file__).resolve().parent.parent
DEMO = str(ROOT / "examples" / "demo_trace.jsonl")


def test_cli_autopsy_prints_report(capsys):
    assert main(["autopsy", DEMO]) == 0
    out = capsys.readouterr().out
    assert "r1: stale" in out
    assert "r4: poisoned" in out
    assert "Stale-read rate: 0.200" in out


def test_cli_blame_one_decision(capsys):
    assert main(["autopsy", DEMO, "--blame", "d1"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["decisive_record"] == "r1"
    assert out["causal_records"] == ["r1"]
    assert out["redundant"] is False


def test_cli_blame_unknown_decision_is_error(capsys):
    assert main(["autopsy", DEMO, "--blame", "d99"]) == 2


def test_cli_writes_json_and_markdown(tmp_path, capsys):
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"
    assert main(["autopsy", DEMO, "--json", str(json_path), "--markdown", str(md_path)]) == 0
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["metrics"]["records"] == 6
    assert "Memory Autopsy Report" in md_path.read_text(encoding="utf-8")


def test_cli_simulate_one_scenario(tmp_path, capsys):
    out = tmp_path / "stale.jsonl"
    assert main(["simulate", "--scenario", "stale", "--seed", "7", "--out", str(out)]) == 0
    assert out.exists()
    assert "decisive recovery: 1.000" in capsys.readouterr().out


def test_cli_simulate_unknown_scenario_is_error(capsys):
    assert main(["simulate", "--scenario", "haunted", "--out", "x.jsonl"]) == 2


def test_cli_blame_graph(tmp_path):
    out = tmp_path / "graph.json"
    assert main(["blame-graph", DEMO, "--out", str(out)]) == 0
    graph = json.loads(out.read_text(encoding="utf-8"))
    assert len(graph["nodes"]) == 9
    assert any(e["kind"] == "supersedes" for e in graph["edges"])


def test_cli_as_module(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "memory_autopsy", "--version"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout
