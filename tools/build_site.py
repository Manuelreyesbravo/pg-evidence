#!/usr/bin/env python3
# Copyright 2026 Manuel Reyes Bravo
# SPDX-License-Identifier: Apache-2.0
"""Render site/ from claims/ and results/: plain HTML, no JavaScript, no build step.

    python3 tools/build_site.py

Writes site/index.html, one page per run under site/runs/, and copies every raw file to
site/raw/ so each figure links to the exact bytes it was computed from. The output is
deterministic (no timestamps), so CI can check that the committed site is up to date.
Only site/style.css is written by hand.
"""
import html
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import derive  # noqa: E402
from evidence import CLAIMS, RESULTS, ROOT, check_claim, load_json, run_dirs, sha256  # noqa: E402

SITE = os.path.join(ROOT, "site")
REPO_URL = os.environ.get("PG_EVIDENCE_REPO_URL", "https://github.com/Manuelreyesbravo/pg-evidence")
NAME = "pg-evidence"
e = html.escape


def page(title, body, depth=0):
    up = "../" * depth
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<link rel="stylesheet" href="{up}style.css">
</head>
<body>
<header class="top"><a class="name" href="{up}index.html">{NAME}</a>
<span class="tag">numbers about PostgreSQL extensions, each one rerunnable</span></header>
<main>
{body}
</main>
<footer>Every figure here is recomputed from the raw file it links to (sha256 shown) by
<code>tools/validate.py</code>. Source, schema and the process to submit your own run:
<a href="{e(REPO_URL)}">{e(REPO_URL)}</a>.</footer>
</body>
</html>
"""


def run_slug(key):
    return key.replace("/", "--")


def fmt(v):
    if v is None:
        return '<span class="na">not recorded</span>'
    if isinstance(v, bool):
        return "yes" if v else "no"
    return e(str(v))


def kv_table(rows):
    out = ['<table class="kv">']
    for k, v in rows:
        out.append(f"<tr><th>{e(k)}</th><td>{v}</td></tr>")
    out.append("</table>")
    return "\n".join(out)


def build():
    if os.path.isdir(os.path.join(SITE, "runs")):
        shutil.rmtree(os.path.join(SITE, "runs"))
    if os.path.isdir(os.path.join(SITE, "raw")):
        shutil.rmtree(os.path.join(SITE, "raw"))
    os.makedirs(os.path.join(SITE, "runs"))

    runs = {}
    for run_dir in run_dirs():
        key = os.path.relpath(run_dir, RESULTS).replace(os.sep, "/")
        result = load_json(os.path.join(run_dir, "result.json"))
        runs[key] = (run_dir, result, derive.derive(run_dir, result))
        raw_dest = os.path.join(SITE, "raw", key)
        os.makedirs(raw_dest)
        for item in result["raw"]:
            shutil.copyfile(os.path.join(run_dir, item["path"]), os.path.join(raw_dest, item["path"]))

    benches = {}
    bdir = os.path.join(ROOT, "benchmarks")
    for name in sorted(os.listdir(bdir)):
        meta = os.path.join(bdir, name, "benchmark.json")
        if os.path.isfile(meta):
            benches[name] = load_json(meta)

    claims = load_json(CLAIMS)["claims"]
    figures_by_run = {k: v[2] for k, v in runs.items()}

    # -- index ------------------------------------------------------------------------------
    body = ["""<section class="lede">
<h1>Every number, with the run behind it</h1>
<p>Each figure below is a published claim about the pg_agent_gate / pg_phasevec family of
PostgreSQL extensions. Each one links to the run that produced it: the versions, the
hardware, the commit, the raw data and its sha256, and the one command that reruns it.
If a rerun disagrees, submit it: a number claims, the machine decides.</p>
</section>
<section><h2>Claims</h2>"""]
    for c in claims:
        ok, lines = check_claim(c, figures_by_run)
        run_dir, result, _ = runs[c["run"]]
        r = result["run"]
        raw = result["raw"][0]
        checks = "".join(
            f"<li><code>{e(ch['figure'])}</code> "
            f"{'(' + e(ch['transform']) + ') ' if ch.get('transform') else ''}"
            f"= {fmt(figures_by_run[c['run']].get(ch['figure']))} → {fmt(ch['equals'])}</li>"
            for ch in c["checks"])
        links = [f'<a href="runs/{run_slug(c["run"])}.html">the run</a>']
        if r.get("run_url"):
            links.append(f'<a href="{e(r["run_url"])}">CI log</a>')
        links.append(f'<a href="raw/{e(c["run"])}/{e(raw["path"])}">raw data</a> '
                     f'<code class="sha">sha256 {e(raw["sha256"][:16])}…</code>')
        body.append(f"""<article class="claim" id="{e(c['id'])}">
<p class="text">{e(c['text'])}</p>
<p class="verdict {'ok' if ok else 'bad'}">{'Supported by the raw data' if ok else 'NOT supported by the raw data'}</p>
<details><summary>How it is computed</summary><ul class="checks">{checks}</ul>
<p>Recompute it yourself: <code>make claim-{e(c['id'])}</code></p></details>
<p class="links">{' · '.join(links)}</p>
</article>""")
    body.append("</section>\n<section><h2>Benchmarks</h2>")
    for name, b in benches.items():
        bruns = [(k, v) for k, v in runs.items() if k.startswith(name + "/")]
        items = "".join(
            f'<li><a href="runs/{run_slug(k)}.html">{e(v[1]["id"])}</a> '
            f'<span class="status {e(v[1]["status"])}">{e(v[1]["status"])}</span> '
            f'{e(v[1]["date"])}</li>' for k, v in bruns) or "<li>No runs yet.</li>"
        caveats = "".join(f"<li>{e(x)}</li>" for x in b.get("caveats", []))
        body.append(f"""<article class="bench" id="{e(name)}">
<h3>{e(b['title'])} <span class="status {e(b['status'])}">{e(b['status'])}</span></h3>
<p>{e(b['measures'])}</p>
<p>Rerun: <code>{e(b['rerun'])}</code></p>
<ul class="caveats">{caveats}</ul>
<h4>Runs</h4><ul>{items}</ul>
</article>""")
    body.append("</section>")
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
        f.write(page(NAME, "\n".join(body)))

    # -- one page per run -------------------------------------------------------------------
    for key, (run_dir, result, figures) in runs.items():
        r = result["run"]
        rows = [("benchmark", e(result["benchmark"])), ("status", e(result["status"])),
                ("date", e(result["date"])), ("submitted by", e(result["submitted_by"])),
                ("configuration", e(r["config"])),
                ("harness", f'<a href="{e(r["harness_repo"])}">{e(r["harness_repo"])}</a> '
                            f'at <code>{e(r["harness_commit"])}</code>'),
                ("CI run", f'<a href="{e(r["run_url"])}">{e(r["run_url"])}</a>' if r.get("run_url") else fmt(None)),
                ("rerun", f'<code>{e(r.get("command", ""))}</code>'),
                ("repetitions", fmt(r["repeat"])),
                ("seed", f'{fmt(r["seed"]["value"])} — {e(r["seed"]["note"])}')]
        versions = [(k, fmt(v)) for k, v in r["versions"].items()]
        model = [(k, fmt(v)) for k, v in r.get("model", {}).items()]
        hw = [(k, fmt(v)) for k, v in r["hardware"].items()]
        raw = "".join(
            f'<tr><td><a href="../raw/{e(key)}/{e(i["path"])}">{e(i["path"])}</a></td>'
            f'<td><code class="sha">{e(i["sha256"])}</code></td>'
            f'<td>{"ok" if sha256(os.path.join(run_dir, i["path"])) == i["sha256"] else "MISMATCH"}</td></tr>'
            for i in result["raw"])
        figs = kv_table([(k, fmt(v)) for k, v in sorted(figures.items())])
        notes = f'<p class="notes">{e(result["notes"])}</p>' if result.get("notes") else ""
        body = f"""<h1>{e(result['benchmark'])} / {e(result['id'])}</h1>
{notes}
<h2>The run</h2>{kv_table(rows)}
<h2>Versions</h2>{kv_table(versions)}
{"<h2>Model</h2>" + kv_table(model) if model else ""}
<h2>Hardware</h2>{kv_table(hw)}
<h2>Raw data</h2>
<div class="scroll"><table class="raw"><tr><th>file</th><th>sha256</th><th>check</th></tr>{raw}</table></div>
<h2>Figures (recomputed from the raw data)</h2>{figs}"""
        with open(os.path.join(SITE, "runs", run_slug(key) + ".html"), "w", encoding="utf-8") as f:
            f.write(page(f"{result['benchmark']} / {result['id']} — {NAME}", body, depth=1))
    print(f"site: {len(claims)} claims, {len(runs)} runs, {len(benches)} benchmarks")


if __name__ == "__main__":
    build()
