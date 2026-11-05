#!/usr/bin/env python3
# Copyright 2026 Manuel Reyes Bravo
# SPDX-License-Identifier: Apache-2.0
"""Compute a run's figures from its raw files. The only place a number is made.

Every figure the site shows, and every published claim, is recomputed here from the raw
file whose sha256 the result records. A result.json may carry figures, but only to be
compared with what this module computes: if they differ, validation fails.

    python3 tools/derive.py results/<benchmark>/<run-id>     # print the figures as JSON
"""
import json
import os
import sys


def _load(run_dir, name):
    with open(os.path.join(run_dir, name), encoding="utf-8") as f:
        return json.load(f)


def _arms(summary):
    return {row["arm"]: row for row in summary}


def agent_gate_compare(run_dir, raw):
    """Figures of the same-gate, with/without-MCP comparison (agent-gate-demo/compare)."""
    data = _load(run_dir, raw[0]["path"])
    arms = _arms(data["summary"])
    fig = {}
    for name, row in sorted(arms.items()):
        key = name.replace("-", "_")
        fig[f"{key}.good"] = f'{row["good_ok"]}/{row["good_total"]}'
        fig[f"{key}.breach"] = f'{row["breach"]}/{row["traps_total"]}'
        fig[f"{key}.bounded"] = f'{row["bounded"]}/{row["traps_total"]}'
        fig[f"{key}.prompt_tokens_total"] = row["prompt_tokens_total"]
        fig[f"{key}.model_calls_total"] = row["model_calls_total"]
        fig[f"{key}.median_seconds"] = row["median_seconds"]
        fig[f"{key}.errors"] = row["errors"]
    gated = [a for a in ("native", "native-loop", "gated-mcp") if a in arms]
    if gated:
        worst = max(gated, key=lambda a: arms[a]["breach"])
        fig["gated.max_breach"] = f'{arms[worst]["breach"]}/{arms[worst]["traps_total"]}'
    if "gated-mcp" in arms and "native-loop" in arms:
        mcp, loop = arms["gated-mcp"], arms["native-loop"]
        fig["ratio.prompt_tokens.gated_mcp_over_native_loop"] = round(
            mcp["prompt_tokens_total"] / loop["prompt_tokens_total"], 3)
        fig["ratio.median_seconds.gated_mcp_over_native_loop"] = round(
            mcp["median_seconds"] / loop["median_seconds"], 3)
    fig["tasks.per_arm"] = len({r["id"] for r in data["results"]})
    fig["results.rows"] = len(data["results"])
    return fig


def image_preflight(run_dir, raw):
    """Figures of a Red Hat preflight `check container` run (its stdout JSON)."""
    data = _load(run_dir, raw[0]["path"])
    res = data.get("results", {})
    passed, failed, errors = (len(res.get(k) or []) for k in ("passed", "failed", "errors"))
    return {
        "checks.passed": passed,
        "checks.failed": failed,
        "checks.errors": errors,
        "checks.total": passed + failed + errors,
        "passed": bool(data.get("passed")),
        "preflight.version": data.get("test_library", {}).get("version", ""),
        "image": data.get("image", ""),
    }


def phasevec_recall(run_dir, raw):
    """Figures of a pg_phasevec vs pgvector recall run (benchmarks/phasevec-recall)."""
    data = _load(run_dir, raw[0]["path"])
    fig = {}
    for p in data["points"]:
        key = f'{p["engine"]}.{p["index"]}.{p["param_name"]}={p["param_value"]}'
        fig[f"{key}.recall_at_{data['k']}"] = round(p["recall"], 4)
        fig[f"{key}.p50_ms"] = round(p["p50_ms"], 3)
        fig[f"{key}.p99_ms"] = round(p["p99_ms"], 3)
    return fig


DERIVERS = {
    "agent-gate-compare": agent_gate_compare,
    "image-preflight": image_preflight,
    "phasevec-recall": phasevec_recall,
}


def derive(run_dir, result):
    try:
        fn = DERIVERS[result["benchmark"]]
    except KeyError:
        raise SystemExit(f"no deriver for benchmark {result['benchmark']!r}")
    return fn(run_dir, result["raw"])


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    run_dir = sys.argv[1]
    result = _load(run_dir, "result.json")
    print(json.dumps(derive(run_dir, result), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
