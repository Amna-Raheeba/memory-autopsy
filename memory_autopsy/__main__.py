"""Command line interface.

Usage (from the repo root):

    python -m memory_autopsy autopsy examples/demo_trace.jsonl
    python -m memory_autopsy autopsy trace.jsonl --json report.json
    python -m memory_autopsy autopsy trace.jsonl --markdown report.md
    python -m memory_autopsy autopsy trace.jsonl --blame d3
    python -m memory_autopsy simulate --seed 7 --per-scenario 50 --out results/traces.jsonl
    python -m memory_autopsy blame-graph trace.jsonl --out graph.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from memory_autopsy import __version__
from memory_autopsy.attribution import attribute_decision, blame_graph
from memory_autopsy.diagnosis import diagnose_trace
from memory_autopsy.evaluate import score_dataset, score_trace
from memory_autopsy.report import aggregate, json_report, markdown_report
from memory_autopsy.simulate import SCENARIOS, generate_dataset, generate_trace
from memory_autopsy.trace import load_trace, trace_to_jsonl


def _cmd_autopsy(args: argparse.Namespace) -> int:
    trace = load_trace(args.trace)
    autopsy = diagnose_trace(trace)
    if args.blame:
        decision = trace.decisions.get(args.blame)
        if decision is None:
            print("unknown decision %r" % args.blame, file=sys.stderr)
            return 2
        print(json.dumps(attribute_decision(trace, decision), indent=2, sort_keys=True))
        return 0
    if args.json:
        Path(args.json).write_text(json_report(trace, autopsy), encoding="utf-8")
        print("wrote %s" % args.json)
    if args.markdown:
        Path(args.markdown).write_text(markdown_report(trace, autopsy), encoding="utf-8")
        print("wrote %s" % args.markdown)
    if not args.json and not args.markdown:
        print(markdown_report(trace, autopsy))
    else:
        metrics = aggregate(trace, autopsy)
        print(
            "records=%d reads=%d decisions=%d stale_read_rate=%.3f "
            "poison_influence_rate=%.3f contradiction_rate=%.3f"
            % (
                metrics["records"],
                metrics["reads"],
                metrics["decisions"],
                metrics["stale_read_rate"],
                metrics["poison_influence_rate"],
                metrics["contradiction_rate"],
            )
        )
    return 0


def _cmd_simulate(args: argparse.Namespace) -> int:
    if args.scenario and args.scenario not in SCENARIOS:
        print("unknown scenario %r" % args.scenario, file=sys.stderr)
        return 2
    if args.scenario:
        trace, truth = generate_trace(args.scenario, args.seed, args.n_decisions)
        Path(args.out).write_text(trace_to_jsonl(trace), encoding="utf-8")
        score = score_trace(trace, truth)
        print("wrote %s (%s, seed %d)" % (args.out, args.scenario, args.seed))
        print("decisive recovery: %.3f" % score["decisive_recovery"])
    else:
        dataset = generate_dataset(args.seed, args.per_scenario, args.n_decisions)
        with Path(args.out).open("w", encoding="utf-8") as handle:
            for scenario, trace, _truth in dataset:
                handle.write("# scenario=%s\n" % scenario)
                handle.write(trace_to_jsonl(trace))
        scored = [
            (scenario, score_trace(trace, truth)) for scenario, trace, truth in dataset
        ]
        evaluation = score_dataset(scored)
        print("wrote %s (%d traces)" % (args.out, len(dataset)))
        print("decisive recovery: %.3f" % evaluation["decisive_recovery"])
        for verdict, cell in evaluation["per_verdict"].items():
            if cell["tp"] + cell["fp"] + cell["fn"]:
                print(
                    "  %-13s P=%s R=%s (tp=%d fp=%d fn=%d)"
                    % (
                        verdict,
                        _fmt(cell["precision"]),
                        _fmt(cell["recall"]),
                        cell["tp"],
                        cell["fp"],
                        cell["fn"],
                    )
                )
    return 0


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else "%.3f" % value


def _cmd_blame_graph(args: argparse.Namespace) -> int:
    trace = load_trace(args.trace)
    graph = blame_graph(trace)
    if args.out:
        Path(args.out).write_text(
            json.dumps(graph, indent=2, sort_keys=True), encoding="utf-8"
        )
        print("wrote %s" % args.out)
    else:
        print(json.dumps(graph, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memory-autopsy",
        description="Post-mortem diagnosis of an agent's memory system.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    sub = parser.add_subparsers(dest="command", required=True)

    autopsy = sub.add_parser("autopsy", help="autopsy one trace file")
    autopsy.add_argument("trace", help="path to a JSONL trace file")
    autopsy.add_argument("--json", help="write the full JSON report here")
    autopsy.add_argument("--markdown", help="write the Markdown report here")
    autopsy.add_argument("--blame", help="show attribution for one decision id")
    autopsy.set_defaults(func=_cmd_autopsy)

    simulate = sub.add_parser("simulate", help="generate seeded traces")
    simulate.add_argument("--seed", type=int, default=7)
    simulate.add_argument("--per-scenario", type=int, default=50)
    simulate.add_argument("--n-decisions", type=int, default=5)
    simulate.add_argument("--scenario", help="one scenario, or all five if omitted")
    simulate.add_argument("--out", required=True, help="output JSONL path")
    simulate.set_defaults(func=_cmd_simulate)

    graph = sub.add_parser("blame-graph", help="emit the blame graph as JSON")
    graph.add_argument("trace", help="path to a JSONL trace file")
    graph.add_argument("--out", help="write the graph JSON here")
    graph.set_defaults(func=_cmd_blame_graph)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
