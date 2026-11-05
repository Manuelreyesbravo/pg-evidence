#!/usr/bin/env python3
# Copyright 2026 Manuel Reyes Bravo
# SPDX-License-Identifier: Apache-2.0
"""Recompute ONE published claim from its raw data and show every step.

    python3 tools/claim.py <claim-id>      # exit 0 if the raw data supports the claim
    python3 tools/claim.py --list
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import derive  # noqa: E402
from evidence import CLAIMS, RESULTS, check_claim, load_json, sha256  # noqa: E402


def main():
    claims = {c["id"]: c for c in load_json(CLAIMS)["claims"]}
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    if sys.argv[1] == "--list":
        for cid, c in claims.items():
            print(f"{cid:28} {c['run']}")
        return 0
    claim = claims.get(sys.argv[1]) or sys.exit(f"no claim {sys.argv[1]!r}; try --list")
    run_dir = os.path.join(RESULTS, claim["run"])
    result = load_json(os.path.join(run_dir, "result.json"))
    print(f"claim:  {claim['text']}")
    print(f"run:    results/{claim['run']} ({result['status']})")
    print(f"        {result['run'].get('run_url') or result['run'].get('command')}")
    for item in result["raw"]:
        actual = sha256(os.path.join(run_dir, item["path"]))
        mark = "ok" if actual == item["sha256"] else "MISMATCH"
        print(f"raw:    {item['path']} sha256 {actual} {mark}")
        if actual != item["sha256"]:
            return 1
    ok, lines = check_claim(claim, {claim["run"]: derive.derive(run_dir, result)})
    print("\n".join(lines))
    print("SUPPORTED by the raw data" if ok else "NOT SUPPORTED by the raw data")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
