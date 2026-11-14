# pg-evidence

Every public number about the **pg_agent_gate / pg_phasevec** family of PostgreSQL
extensions, each tied to the run that produced it: the versions, the hardware, the commit,
the seed, the raw data with its sha256, and the one command that reruns it. A number
claims; the machine decides.

```sh
make validate     # recompute every figure from its raw data and check every claim
make claims       # the same, one published claim at a time, step by step
make site         # render site/ (plain HTML, light and dark) from results/ and claims/
```

Only `python3` is needed to check everything. No package to install.

## What is here

| path | what |
|---|---|
| `claims/claims.json` | every published claim, its exact wording, the run it cites, and the checks that recompute it |
| `results/schema.json` | the format of a run: metadata (versions, hardware, seed, commits) + raw files by sha256 |
| `results/<benchmark>/<run>/` | `result.json` and the raw files every figure is computed from |
| `benchmarks/<benchmark>/` | what it measures (`benchmark.json`), how to rerun it, its spec |
| `tools/derive.py` | the only code that turns raw data into figures |
| `tools/validate.py` | schema, sha256, figures recomputed, claims checked; CI runs it on every push and PR |
| `tools/claim.py` | one claim, recomputed with every step shown |
| `tools/ingest.py` | turns a downloaded run into a `results/` entry |
| `tools/build_site.py` | renders `site/`; every figure links to its run and its raw file |
| `site/` | the static page (generated, except `style.css`) |

## The benchmarks

### agent-gate-compare: the same gate, with and without MCP — cited

**Measures.** One model (base Qwen3-8B Q4_K_M, not fine-tuned, temperature 0), 13 tasks (6
everyday, 7 traps) and a superuser oracle that compares every table before and after each
task. Only the connection changes: `native` (one SQL statement through pg_agent_gate),
`native-loop` (the same, agentic), `gated-mcp` (the same gate over MCP) and `stock-mcp` (a
popular Postgres MCP server, same privileges, no gate). Per arm: good tasks done, trap
breaches, prompt tokens, model calls, median seconds per task, errors.

**Cited run.** [agent-gate-demo run 41184106078](https://github.com/Manuelreyesbravo/agent-gate-demo/actions/runs/41184106078),
1 repetition, raw file `compare-results.json` (sha256 `8207e5a3…826f`).

| | pinned |
|---|---|
| harness | agent-gate-demo `4cef786` |
| pg_agent_gate | 0.4.0 (`33d0acb`), built from source |
| PostgreSQL | 18 from apt.postgresql.org (minor not recorded by that run) |
| llama.cpp | `bd4eeaa`, CPU build |
| model | unsloth Qwen3-8B-Q4_K_M.gguf, sha256 `120307ba…`, **context 4096 tokens** |
| stock MCP | crystaldba/postgres-mcp, by digest |
| hardware | GitHub-hosted ubuntu-24.04 runner, CPU only, no GPU (core count and CPU model not recorded by that run) |
| seed | none: temperature 0, greedy decoding |

**Rerun.** From your fork of agent-gate-demo: `gh workflow run compare.yml -f config=cited`,
or `make rerun-agent-gate-compare FORK=you/agent-gate-demo`, which also downloads the
artifact and ingests it here as a submitted run. New runs record the PostgreSQL minor,
CPU, cores and memory in `run-metadata.json`.

**Read it with this in mind.** 13 tasks is a demonstration, not a statistical benchmark.
The 4096-token context is small for the MCP arms, which carry tool definitions and tool
results in it (one gated-mcp error in the cited run was a context overflow). The cited run
measured gate 0.4.0 on PostgreSQL 18; the public image ygg-pg 0.3.6 ships 0.4.3 on PostgreSQL
19rc2, and `config=current` measures 0.4.3.

Claims that cite it: `trap-breakouts`, `mcp-tokens-and-time`, `one-statement-median`.

### image-preflight: Red Hat's preflight on the public image — cited

**Measures.** `preflight check container` (openshift-preflight 1.22.0, `1195775`) on
`ghcr.io/latamflows/ygg-pg:0.3.5`, by digest `sha256:9962ad3f…`, pulled with no registry
credential. Checks passed, failed, errored. Deterministic; no seed. Passing preflight is a
prerequisite for container certification, not the certification.

**Rerun.** `make rerun-image-preflight` (needs the `preflight` binary).

Claim that cites it: `image-preflight`.

### phasevec-recall: pg_phasevec vs pgvector — designed, not run

recall@10 against the dataset's own ground truth and per-query latency, for pg_phasevec
(`find`, `find_ivf`) and pgvector (HNSW, IVFFlat), same vectors, same queries, same
PostgreSQL build, same machine, each swept over its own search knob, reported as curves.
Spec: [benchmarks/phasevec-recall/SPEC.md](benchmarks/phasevec-recall/SPEC.md). Script
skeleton: `benchmarks/phasevec-recall/run_recall.py --plan`. No figure from it is published.

## Submit your run

See [SUBMITTING.md](SUBMITTING.md). In short: rerun, `tools/ingest.py` it, open a pull
request adding `results/<benchmark>/<your-run>/`. CI recomputes every figure from your raw
files; it never trusts a number typed by hand. Your run is shown next to the cited one,
whatever it says.

## Rules this repository keeps

- A published number exists here, as a claim that passes `make validate`, or it is not
  published.
- A figure is computed from raw data by `tools/derive.py`; stored figures are only
  compared with it.
- "Not recorded" is `null`, never a guess.
- Times from a machine shared with other work are shown but never cited.
- Ratios are shown together with the two values they divide, and with the run's caveats.

## License

Apache-2.0. See [LICENSE](LICENSE).
