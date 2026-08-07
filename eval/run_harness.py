"""Eval harness: runs the PatchPilot agent against every bug in
eval/bug_bank and produces eval/results/harness_report.json with
per-bug results and an honest per-difficulty-tier breakdown.

Usage:
    python eval/run_harness.py [--bug-bank eval/bug_bank] [--out eval/results/harness_report.json]

Requires GROQ_API_KEY to be set (the agent makes real chat-completions API
calls). Each bug gets its own run_id under runs/eval_<bug_id>/.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.core import run_agent  # noqa: E402

DIFFICULTIES = ["easy", "medium", "hard"]

# USD per 1M tokens, Groq's published list pricing as of 2026-08
# (https://console.groq.com/docs/model/openai/gpt-oss-120b). Update this if
# the configured model or Groq's rates change - these are list prices for
# cost estimation, not pulled from a live billing API.
PRICING_PER_MILLION_TOKENS_USD = {
    "openai/gpt-oss-120b": {"input": 0.15, "output": 0.60},
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    rates = PRICING_PER_MILLION_TOKENS_USD.get(model)
    if rates is None:
        return None
    return (input_tokens / 1_000_000) * rates["input"] + (output_tokens / 1_000_000) * rates["output"]


def discover_bugs(bug_bank_dir: Path) -> list[dict]:
    bugs = []
    for bug_dir in sorted(bug_bank_dir.iterdir()):
        metadata_path = bug_dir / "metadata.json"
        repo_path = bug_dir / "repo"
        if not metadata_path.exists() or not repo_path.exists():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        bugs.append(
            {
                "bug_id": bug_dir.name,
                "repo_path": repo_path,
                "difficulty": metadata.get("difficulty", "unknown"),
                "bug_type": metadata.get("bug_type", "unknown"),
                "description": metadata.get("description", ""),
            }
        )
    return bugs


def classify_failure_mode(result: dict) -> str | None:
    if result["success"]:
        return None
    if result.get("last_hypothesis"):
        return "gave_up_with_hypothesis"
    return "gave_up_no_hypothesis"


def run_single_bug(bug: dict, runs_dir: Path, max_iterations: int) -> dict:
    run_id = f"eval_{bug['bug_id']}"
    started = time.monotonic()
    try:
        report = run_agent(
            source_repo_path=bug["repo_path"],
            run_id=run_id,
            runs_dir=runs_dir,
            max_iterations=max_iterations,
        )
        error = None
    except Exception as exc:  # noqa: BLE001
        report = {
            "run_id": run_id,
            "success": False,
            "iterations": 0,
            "last_hypothesis": None,
            "summary": None,
            "input_tokens": 0,
            "output_tokens": 0,
        }
        error = f"{type(exc).__name__}: {exc}"
    wall_clock = time.monotonic() - started
    input_tokens = report.get("input_tokens", 0)
    output_tokens = report.get("output_tokens", 0)
    model = os.environ.get("PATCHPILOT_MODEL", "openai/gpt-oss-120b")

    result = {
        "bug_id": bug["bug_id"],
        "difficulty": bug["difficulty"],
        "bug_type": bug["bug_type"],
        "success": report["success"],
        "iterations": report["iterations"],
        "wall_clock_seconds": round(wall_clock, 2),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": estimate_cost_usd(model, input_tokens, output_tokens),
        "last_hypothesis": report.get("last_hypothesis"),
        "summary": report.get("summary"),
        "trace_path": str(runs_dir / run_id / "trace.json"),
        "error": error,
    }
    result["failure_mode"] = classify_failure_mode(result)
    return result


def aggregate(results: list[dict]) -> dict:
    by_tier = {}
    for tier in DIFFICULTIES:
        tier_results = [r for r in results if r["difficulty"] == tier]
        if not tier_results:
            by_tier[tier] = {"total": 0, "passed": 0, "pass_rate": None}
            continue
        passed = sum(1 for r in tier_results if r["success"])
        by_tier[tier] = {
            "total": len(tier_results),
            "passed": passed,
            "pass_rate": round(passed / len(tier_results), 3),
        }

    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]

    failure_modes: dict[str, int] = {}
    for r in failures:
        mode = r["failure_mode"] or "unknown"
        failure_modes[mode] = failure_modes.get(mode, 0) + 1

    # Latency (wall-clock) is only meaningful for runs that actually
    # exercised the model to convergence or gave up cleanly - a run that hit
    # the retry-and-give-up path is mostly measuring provider flakiness, not
    # agent behavior, so it's excluded from the latency stats below (it's
    # still counted in pass/fail and cost).
    reasoning_results = [
        r for r in results if r["failure_mode"] != "gave_up_no_hypothesis" or r["success"]
    ]
    latencies = [r["wall_clock_seconds"] for r in reasoning_results]

    costs = [r["estimated_cost_usd"] for r in results if r["estimated_cost_usd"] is not None]
    success_costs = [r["estimated_cost_usd"] for r in successes if r["estimated_cost_usd"] is not None]

    return {
        "total_bugs": len(results),
        "total_passed": len(successes),
        "overall_pass_rate": round(len(successes) / len(results), 3) if results else None,
        "by_difficulty": by_tier,
        "avg_iterations_to_success": (
            round(statistics.mean(r["iterations"] for r in successes), 2) if successes else None
        ),
        "avg_iterations_to_giveup": (
            round(statistics.mean(r["iterations"] for r in failures), 2) if failures else None
        ),
        "most_common_failure_mode": (
            max(failure_modes, key=failure_modes.get) if failure_modes else None
        ),
        "failure_mode_breakdown": failure_modes,
        "total_input_tokens": sum(r["input_tokens"] for r in results),
        "total_output_tokens": sum(r["output_tokens"] for r in results),
        "total_estimated_cost_usd": round(sum(costs), 4) if costs else None,
        "avg_cost_per_successful_fix_usd": (
            round(statistics.mean(success_costs), 4) if success_costs else None
        ),
        "avg_wall_clock_seconds": round(statistics.mean(latencies), 2) if latencies else None,
        "median_wall_clock_seconds": round(statistics.median(latencies), 2) if latencies else None,
        "p90_wall_clock_seconds": (
            round(statistics.quantiles(latencies, n=10)[8], 2) if len(latencies) >= 2 else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PatchPilot eval harness")
    parser.add_argument("--bug-bank", default="eval/bug_bank")
    parser.add_argument("--out", default="eval/results/harness_report.json")
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--max-iterations", type=int, default=6)
    args = parser.parse_args()

    bug_bank_dir = Path(args.bug_bank)
    bugs = discover_bugs(bug_bank_dir)
    if not bugs:
        print(f"No bugs found under {bug_bank_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Running PatchPilot against {len(bugs)} bugs from {bug_bank_dir}...")
    results = []
    for i, bug in enumerate(bugs, start=1):
        print(f"[{i}/{len(bugs)}] {bug['bug_id']} ({bug['difficulty']})...", end=" ", flush=True)
        result = run_single_bug(bug, Path(args.runs_dir), args.max_iterations)
        status = "PASS" if result["success"] else "FAIL"
        print(f"{status} in {result['iterations']} iterations, {result['wall_clock_seconds']}s")
        results.append(result)

    report = {
        "generated_at": time.time(),
        "results": results,
        "aggregate": aggregate(results),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    agg = report["aggregate"]
    print("\n=== Summary ===")
    print(f"Overall: {agg['total_passed']}/{agg['total_bugs']} ({agg['overall_pass_rate']:.0%})")
    for tier, stats in agg["by_difficulty"].items():
        if stats["total"] == 0:
            continue
        print(f"  {tier}: {stats['passed']}/{stats['total']} ({stats['pass_rate']:.0%})")
    if agg["total_estimated_cost_usd"] is not None:
        print(f"Estimated cost: ${agg['total_estimated_cost_usd']:.4f} total, "
              f"${agg['avg_cost_per_successful_fix_usd']:.4f} avg per successful fix")
    if agg["avg_wall_clock_seconds"] is not None:
        print(f"Latency: avg {agg['avg_wall_clock_seconds']}s, median {agg['median_wall_clock_seconds']}s, "
              f"p90 {agg['p90_wall_clock_seconds']}s")
    print(f"Report written to {out_path}")


if __name__ == "__main__":
    main()
