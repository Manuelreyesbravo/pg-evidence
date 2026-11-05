# pg_phasevec vs pgvector: recall and latency on the same data

Status: **designed, not run**. Nothing from this benchmark is published until a run lands
in `results/phasevec-recall/` and passes `make validate`.

## The question

At the same recall@10, how fast is pg_phasevec's search compared with pgvector's, on the
same vectors, the same queries, the same PostgreSQL build and the same machine? And what
recall does each reach at each setting of its own search knob?

pg_phasevec does more than search (it refuses stale readings, it ties every reading to a
sealed reader). Those guarantees are not measured here; this benchmark measures only the
part a reviewer will compare with pgvector, so the comparison has to be fair to both.

## Data

- **Primary: `nytimes-256-angular`** from ann-benchmarks (290,000 base vectors, 10,000
  queries, 256 dimensions, angular distance, 100 true neighbours per query in the file).
  256 dimensions match pg_phasevec's 256-bit sign code, and the ground truth is the
  dataset's own, computed on the original floats, not by either engine.
- **Secondary (later): `glove-100-angular`** (1.18M x 100) for scale, and one set of real
  sentence embeddings for the use pg_phasevec is built for. Each is a separate run id.
- The file is downloaded once and pinned by sha256 in `params.json`; a mismatch stops the
  run.
- Query sample: the first `n_queries` queries of the test split (default 1,000), so every
  run uses the same ones. No random sampling.

## How each engine gets the vectors

The vectors are L2-normalised once, so cosine, inner product and angular order agree.

- **pgvector**: `vector(256)`, the normalised floats as they are.
- **pg_phasevec** stores what a reader produces: a per-dimension code (`smallint[]`,
  values in [-127, 127]), a 64-bit sketch and a 256-bit sign code. The benchmark's reader is
  fixed and declared:
  - `code[i] = round(127 * x[i] / s)`, clipped to [-127, 127], with one scale `s` for the
    whole dataset: the 99.9th percentile of |x| over the base set, stored in the result;
  - `code256` = the sign bit of each of the 256 dimensions;
  - `code64` = the sign bits of 64 fixed random hyperplanes (seed 20261105, stored).
  It is registered with `reader_register('bench', <sha256 of params.json>, 256)`, and the
  table is a `watch` whose text is the row id, so `next()`/`record()` run unchanged.
- Quantisation loses information that pgvector keeps. So the run also reports the recall
  of an **exact search over the quantised codes** (brute force in Python with numpy):
  the ceiling pg_phasevec can reach with this reader. A gap between that ceiling and the
  index is the index's; a gap between the ceiling and 1.0 is the reader's.

## What is swept

| engine | index | build parameters | search knob swept |
|---|---|---|---|
| pgvector | HNSW, `vector_cosine_ops` | m=16, ef_construction=64 (pgvector defaults) | `hnsw.ef_search` 10, 20, 40, 80, 120, 200, 400 |
| pgvector | IVFFlat, `vector_cosine_ops` | lists = rows/1000 (290) | `ivfflat.probes` 1, 2, 4, 8, 16, 32, 64 |
| pg_phasevec | `find` (sweep, no index) | none | `p_m` 50, 100, 200, 400, 800 |
| pg_phasevec | `find_ivf` | `ivf_build(watch)` defaults (k, 8 iterations) | `p_nprobe` 1, 2, 4, 8, 16, 32 at `p_m` 200; then `p_m` at the best nprobe |

Every engine's defaults are used for building; only the documented search knob moves.
Nobody tunes one engine and leaves the other at defaults.

## What is reported (per point of each sweep)

- **recall@10**: |returned top 10 ∩ true top 10| / 10, averaged over the queries, where
  "true" is the dataset's ground truth. pg_phasevec rows whose state is not `fresh`
  count as misses (there should be none: nothing is edited during the run).
- **latency**: p50 and p99 per query in milliseconds, measured by the client around one
  `SELECT` per query, prepared statements, one connection, after one untimed warm-up pass
  over all queries.
- **throughput** (second phase): queries per second with 1, 4 and 16 clients, at the
  setting of each engine that first reaches recall@10 ≥ 0.95.
- **build**: wall time to build each index, and its size (`pg_relation_size` for
  pgvector; for pg_phasevec, the size of its tables for this watch).
- The headline is a **recall/latency curve per engine**, never a single number: a
  single "X times faster" hides the recall it was bought at.

## Fixed environment (recorded in result.json)

- One PostgreSQL build for both engines (major 18; the minor, configure flags and
  `pg_config --version` recorded). `shared_buffers` large enough to hold every table and
  index (4GB for nytimes-256), `jit = off`, `max_parallel_workers_per_gather = 0`, the
  same `work_mem` (64MB) for both.
- pgvector at a tag (proposed: v0.8.1) and pg_phasevec at a tag (proposed: v0.18.0, the
  latest tag on GitHub), each with its commit sha.
- The machine: CPU model, cores, RAM, governor, kernel; nothing else running. A run on a
  shared machine is stored with `"shared": true` and its latencies are never cited.
- Determinism: query order fixed; the code64 hyperplanes seeded; pgvector's HNSW level
  assignment and pg_phasevec's k-means are not seedable from SQL, so each index is built
  **3 times** and each point is reported as the median of the 3 builds, with min and max.

## Raw data and result

The script writes `phasevec-recall.json`:

```json
{"dataset": "nytimes-256-angular", "dataset_sha256": "...", "k": 10, "n_queries": 1000,
 "reader": {"scale": 0.0, "code64_seed": 20261105},
 "ceiling_recall_quantised": 0.0,
 "builds": [{"engine": "pgvector", "index": "hnsw", "build": 1, "seconds": 0.0, "bytes": 0}],
 "points": [{"engine": "pgvector", "index": "hnsw", "param_name": "ef_search",
             "param_value": 40, "build": 1, "recall": 0.0, "p50_ms": 0.0, "p99_ms": 0.0,
             "per_query": [[0, 10, 0.0]]}]}
```

`per_query` keeps (query index, hits in the top 10, milliseconds) for every query, so any
summary can be recomputed. `tools/derive.py` turns `points` into figures.

## Run it

```sh
make recall-phasevec DSN=postgresql://postgres@127.0.0.1:5432/bench DATASET=nytimes-256-angular
```

The database must be a throwaway named `bench`; the script refuses any other.

## What it does not show

- Behaviour under writes (pg_phasevec's stale handling, index absorb): a separate
  benchmark.
- GPU/NPU readers, or the quality of any real embedding model: the reader here is a fixed
  quantiser, chosen to be easy to reproduce, not to be good.
