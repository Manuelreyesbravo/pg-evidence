#!/usr/bin/env python3
# Copyright 2026 Manuel Reyes Bravo
# SPDX-License-Identifier: Apache-2.0
"""A number claims, the machine decides.

For every results/<benchmark>/<id>/result.json:
  1. it matches results/schema.json, and its directory names match its benchmark and id;
  2. every raw file it lists exists and has exactly the sha256 it records;
  3. the figures, recomputed from the raw files by tools/derive.py, equal the stored ones.
Then every claim in claims/claims.json is recomputed from the run it names.

    python3 tools/validate.py                      # everything; exit 1 on any failure
    python3 tools/validate.py --write              # (maintainers) store the derived figures
    python3 tools/validate.py --submitted A B ...  # also require these result.json files to
                                                   # be status "submitted" (used on PRs)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import derive  # noqa: E402
from evidence import (CLAIMS, ROOT, SCHEMA, check_claim, check_schema, load_json,  # noqa: E402
                      run_dirs, sha256)


def validate_run(run_dir, schema, write):
    errs = []
    path = os.path.join(run_dir, "result.json")
    result = load_json(path)
    errs += check_schema(result, schema)
    if errs:
        return errs, None
    bench, rid = os.path.basename(os.path.dirname(run_dir)), os.path.basename(run_dir)
    if result["benchmark"] != bench or result["id"] != rid:
        errs.append(f"lives in results/{bench}/{rid} but says {result['benchmark']}/{result['id']}")
    for item in result["raw"]:
        f = os.path.join(run_dir, item["path"])
        if not os.path.isfile(f):
            errs.append(f"raw file missing: {item['path']}")
        elif sha256(f) != item["sha256"]:
            errs.append(f"sha256 mismatch: {item['path']} is {sha256(f)}, result says {item['sha256']}")
    if errs:
        return errs, None
    figures = derive.derive(run_dir, result)
    if write:
        result["figures"] = figures
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=False)
            f.write("\n")
    elif json.loads(json.dumps(result["figures"])) != json.loads(json.dumps(figures)):
        for k in sorted(set(figures) | set(result["figures"])):
            if figures.get(k) != result["figures"].get(k):
                errs.append(f"figure {k}: stored {result['figures'].get(k)!r}, "
                            f"raw data gives {figures.get(k)!r}")
    if result["status"] == "cited" and not (result["run"].get("run_url") or result["run"].get("command")):
        errs.append("a cited run needs a run_url or a command that reruns it")
    return errs, figures


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--submitted", nargs="*", default=[])
    args = ap.parse_args()

    schema = load_json(SCHEMA)
    failed = False
    figures_by_run, status_by_run = {}, {}
    for run_dir in run_dirs():
        rel = os.path.relpath(run_dir, ROOT)
        errs, figures = validate_run(run_dir, schema, args.write)
        if errs:
            failed = True
            print(f"FAIL {rel}")
            for e in errs:
                print(f"     {e}")
        else:
            print(f"ok   {rel}")
            key = rel.split(os.sep, 1)[1].replace(os.sep, "/")
            figures_by_run[key] = figures
            status_by_run[key] = load_json(os.path.join(run_dir, "result.json"))["status"]

    for path in args.submitted:
        if load_json(path)["status"] != "submitted":
            failed = True
            print(f"FAIL {path}: a new run enters as status \"submitted\"; "
                  "only a maintainer promotes a run to \"cited\"")

    for claim in load_json(CLAIMS)["claims"]:
        ok, lines = check_claim(claim, figures_by_run)
        if status_by_run.get(claim["run"]) != "cited":
            ok = False
            lines.append(f"  FAIL run {claim['run']} is not status \"cited\"")
        failed |= not ok
        print(f"{'ok  ' if ok else 'FAIL'} claim {claim['id']}")
        for line in lines:
            print(line)

    print("FAILED" if failed else "all checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
