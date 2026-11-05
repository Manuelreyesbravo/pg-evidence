#!/usr/bin/env python3
# Copyright 2026 Manuel Reyes Bravo
# SPDX-License-Identifier: Apache-2.0
"""Turn a downloaded run into results/<benchmark>/<id>/ (status "submitted").

    python3 tools/ingest.py agent-gate-compare <artifact-dir> --by "Your Name" [--id ID]
    python3 tools/ingest.py image-preflight <dir-with-stdout.json> --by "Your Name" \
        --image-digest sha256:... --preflight-commit <40 hex> [--id ID]

For agent-gate-compare, <artifact-dir> is what `gh run download` writes for the artifact
compare-results-<config>: compare-results.json, run-metadata.json and SHA256SUMS. The
SHA256SUMS the runner printed must match the files, or nothing is written.
"""
import argparse
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import derive  # noqa: E402
from evidence import RESULTS, load_json, sha256  # noqa: E402


def check_sums(src):
    sums = os.path.join(src, "SHA256SUMS")
    if not os.path.isfile(sums):
        sys.exit("no SHA256SUMS in the artifact: download the whole artifact")
    for line in open(sums, encoding="utf-8"):
        digest, name = line.split()
        if sha256(os.path.join(src, name)) != digest:
            sys.exit(f"{name} does not match the SHA256SUMS the runner printed")


def from_compare(src, by, rid):
    check_sums(src)
    meta = load_json(os.path.join(src, "run-metadata.json"))
    run_id = meta["run_url"].rstrip("/").rsplit("/", 1)[-1]
    rid = rid or f"ci-{run_id}"
    v = meta["versions"]
    hw = meta["hardware"]
    result = {
        "schema_version": 1,
        "benchmark": "agent-gate-compare",
        "id": rid,
        "status": "submitted",
        "date": None,
        "submitted_by": by,
        "run": {
            "config": meta["config"],
            "harness_repo": "https://github.com/Manuelreyesbravo/agent-gate-demo",
            "harness_commit": meta["harness_commit"],
            "workflow_commit": meta["workflow_commit"],
            "run_url": meta["run_url"],
            "command": f"gh workflow run compare.yml -f config={meta['config']}",
            "repeat": meta["repeat"],
            "seed": {"value": None, "note": "No sampling seed: temperature 0 (greedy decoding)."},
            "versions": {
                "postgresql_major": v["postgresql_major"],
                "postgresql_server_version": v["postgresql_server_version"] or None,
                "pg_agent_gate": (v["pg_agent_gate_extversion"] or v["pg_agent_gate_tag"].lstrip("v")),
                "pg_agent_gate_commit": v["pg_agent_gate_commit"],
                "llama_cpp_commit": v["llama_cpp_commit"],
                "stock_mcp_image": v["stock_mcp_image"],
            },
            "model": {
                "url": meta["model"]["url"],
                "sha256": meta["model"]["sha256"],
                "context_tokens": meta["model"]["context_tokens"],
                "temperature": meta["model"]["temperature"],
            },
            "hardware": {
                "kind": "github-hosted",
                "label": hw.get("runner", ""),
                "cpu": hw.get("cpu") or None,
                "nproc": hw.get("nproc"),
                "mem_gib": round(hw["mem_kb"] / 1048576, 1) if hw.get("mem_kb") else None,
                "gpu": hw.get("gpu"),
                "shared": False,
            },
        },
        "raw": [],
        "figures": {},
    }
    files = [("compare-results.json", "per-task records and per-arm summary"),
             ("run-metadata.json", "what ran, on what, from which commit")]
    return result, files


def from_preflight(src, by, rid, digest, commit):
    out = load_json(os.path.join(src, "stdout.json"))
    image = out["image"]
    rid = rid or re.sub(r"[^a-z0-9.-]+", "-", image.rsplit("/", 1)[-1].lower())
    result = {
        "schema_version": 1,
        "benchmark": "image-preflight",
        "id": rid,
        "status": "submitted",
        "date": None,
        "submitted_by": by,
        "run": {
            "config": "check container",
            "harness_repo": "https://github.com/redhat-openshift-ecosystem/openshift-preflight",
            "harness_commit": commit,
            "workflow_commit": None,
            "run_url": None,
            "command": f"preflight check container {image.split(':')[0]}@{digest}",
            "repeat": 1,
            "seed": {"value": None, "note": "No randomness."},
            "versions": {"preflight": out["test_library"]["version"], "image": image,
                         "image_digest": digest},
            "hardware": {"kind": "workstation", "cpu": None, "nproc": None, "mem_gib": None,
                         "gpu": None},
        },
        "raw": [],
        "figures": {},
    }
    shutil.copyfile(os.path.join(src, "stdout.json"), os.path.join(src, "preflight-stdout.json"))
    return result, [("preflight-stdout.json", "the JSON preflight prints on stdout")]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("benchmark", choices=["agent-gate-compare", "image-preflight"])
    ap.add_argument("src")
    ap.add_argument("--by", required=True)
    ap.add_argument("--id")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD, the day the run ran (UTC)")
    ap.add_argument("--image-digest")
    ap.add_argument("--preflight-commit")
    args = ap.parse_args()

    if args.benchmark == "agent-gate-compare":
        result, files = from_compare(args.src, args.by, args.id)
    else:
        result, files = from_preflight(args.src, args.by, args.id, args.image_digest,
                                       args.preflight_commit)
    result["date"] = args.date
    dest = os.path.join(RESULTS, args.benchmark, result["id"])
    if os.path.exists(dest):
        sys.exit(f"{dest} exists; pick another --id")
    os.makedirs(dest)
    for name, desc in files:
        shutil.copyfile(os.path.join(args.src, name), os.path.join(dest, name))
        result["raw"].append({"path": name, "sha256": sha256(os.path.join(dest, name)),
                              "description": desc})
    result["figures"] = derive.derive(dest, result)
    with open(os.path.join(dest, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(f"wrote {os.path.relpath(dest)}; now run: make validate site")


if __name__ == "__main__":
    main()
