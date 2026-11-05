#!/usr/bin/env python3
# Copyright 2026 Manuel Reyes Bravo
# SPDX-License-Identifier: Apache-2.0
"""pg_phasevec vs pgvector: recall@k and latency on the same data. SKELETON -- see SPEC.md.

    python3 benchmarks/phasevec-recall/run_recall.py --dsn postgresql://.../bench \
        --dataset nytimes-256-angular [--plan]

--plan prints what would run and exits. Without it the script needs numpy, h5py and
psycopg 3, a throwaway database named `bench` with pgvector and pg_phasevec installable,
and writes phasevec-recall.json for tools/ingest.py. The stages marked TODO are the parts
to finish and review before the first real run; nothing here has produced a figure yet.
"""
import argparse
import hashlib
import json
import os
import statistics
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS = os.path.join(HERE, "params.json")


# -- data -----------------------------------------------------------------------------------
def fetch(dataset, params, cache):
    """Download the HDF5 once; refuse it if its sha256 differs from params.json."""
    spec = params["datasets"][dataset]
    path = os.path.join(cache, f"{dataset}.hdf5")
    if not os.path.exists(path):
        os.makedirs(cache, exist_ok=True)
        urllib.request.urlretrieve(spec["url"], path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()
    if spec["sha256"] is None:
        sys.exit(f"params.json has no sha256 for {dataset} yet; this file is {digest}. "
                 "Pin it in params.json (a reviewed commit) and rerun.")
    if digest != spec["sha256"]:
        sys.exit(f"{path}: sha256 {digest}, params.json pins {spec['sha256']}")
    return path, digest


def load(path, n_queries):
    import h5py
    import numpy as np
    with h5py.File(path, "r") as f:
        train = np.asarray(f["train"], dtype=np.float32)
        test = np.asarray(f["test"][:n_queries], dtype=np.float32)
        truth = np.asarray(f["neighbors"][:n_queries])
    train /= np.linalg.norm(train, axis=1, keepdims=True)
    test /= np.linalg.norm(test, axis=1, keepdims=True)
    return train, test, truth


# -- the declared reader for pg_phasevec (SPEC.md, "How each engine gets the vectors") --------
def reader(train, params):
    import numpy as np
    scale = float(np.percentile(np.abs(train), params["reader"]["scale_percentile"]))
    rng = np.random.default_rng(params["reader"]["code64_seed"])
    planes = rng.standard_normal((64, train.shape[1])).astype(np.float32)

    def codes(x):
        code = np.clip(np.rint(127 * x / scale), -127, 127).astype(np.int16)
        bits256 = "".join("1" if v > 0 else "0" for v in x[:256])
        s64 = 0
        for i, v in enumerate(planes @ x):
            if v > 0:
                s64 |= 1 << i
        if s64 >= 1 << 63:      # bigint is signed
            s64 -= 1 << 64
        return s64, code.tolist(), bits256
    return scale, codes


def quantised_ceiling(train, test, truth, scale, k):
    """Recall of an EXACT search over the quantised codes: the best the reader allows."""
    import numpy as np
    q_train = np.clip(np.rint(127 * train / scale), -127, 127)
    hits = 0
    for i, q in enumerate(test):
        qq = np.clip(np.rint(127 * q / scale), -127, 127)
        top = np.argsort(-(q_train @ qq))[:k]
        hits += len(set(top.tolist()) & set(truth[i][:k].tolist()))
    return hits / (k * len(test))


# -- engines --------------------------------------------------------------------------------
def load_pgvector(conn, train):
    """TODO: COPY the vectors into bench_vec(id int primary key, v vector(256))."""
    raise NotImplementedError("load_pgvector")


def build_pgvector(conn, kind, build):
    """TODO: CREATE INDEX ... USING hnsw (v vector_cosine_ops) WITH (m, ef_construction) or
    ivfflat WITH (lists); return (seconds, pg_relation_size)."""
    raise NotImplementedError("build_pgvector")


def load_phasevec(conn, train, codes, params_sha):
    """TODO: reader_register('bench', params_sha, 256); bench_docs(id int pk, body text);
    watch('bench', 'bench_docs'::regclass, 'id', 'r.body', 'bench'); then for each row of
    next('bench'): record('bench', key, 'bench', text_hash, code64, code, NULL, code256)."""
    raise NotImplementedError("load_phasevec")


def build_phasevec_ivf(conn):
    """TODO: time phasevec.ivf_build('bench') with its defaults; return (seconds, bytes of the
    watch's IVF tables)."""
    raise NotImplementedError("build_phasevec_ivf")


def search_sql(engine, index):
    """The one statement timed per query, per engine (prepared once)."""
    if engine == "pgvector":
        return "SELECT id FROM bench_vec ORDER BY v <=> %s::vector LIMIT %s"
    if index == "find":
        return ("SELECT key, state FROM phasevec.find('bench', %s, %s::smallint[], %s, false, %s,"
                " %s::bit(256))")
    return ("SELECT key, state FROM phasevec.find_ivf('bench', %s, %s::smallint[], %s, false, %s,"
            " %s::bit(256), %s)")


def sweep(conn, engine, index, spec, test, truth, codes, k):
    """TODO: for each value of the knob: SET the knob (pgvector) or pass it (phasevec), one
    untimed pass, then one timed pass; per query keep (i, hits, ms). Rows whose state is not
    'fresh' count as misses."""
    raise NotImplementedError("sweep")


def summarize(per_query, k):
    ms = sorted(x[2] for x in per_query)
    return {
        "recall": sum(x[1] for x in per_query) / (k * len(per_query)),
        "p50_ms": statistics.median(ms),
        "p99_ms": ms[min(len(ms) - 1, int(0.99 * len(ms)))],
    }


# -- main -----------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--dataset", default="nytimes-256-angular")
    ap.add_argument("--cache", default=os.path.join(HERE, "..", "..", "data"))
    ap.add_argument("--out", default="phasevec-recall.json")
    ap.add_argument("--plan", action="store_true", help="print the plan and exit")
    args = ap.parse_args()

    with open(PARAMS, "rb") as f:
        params_bytes = f.read()
    params = json.loads(params_bytes)
    params_sha = hashlib.sha256(params_bytes).hexdigest()
    if args.plan:
        print(f"dataset {args.dataset}, k={params['k']}, {params['n_queries']} queries, "
              f"{params['builds']} builds per index, params sha256 {params_sha}")
        for name, s in params["sweeps"].items():
            print(f"  {name}: build {s['build']}, {s['param']} in {s['values']}")
        return 0

    import psycopg
    with psycopg.connect(args.dsn) as conn:
        if conn.execute("select current_database()").fetchone()[0] != "bench":
            sys.exit("refusing: the database must be a throwaway named bench")
        path, digest = fetch(args.dataset, params, args.cache)
        train, test, truth = load(path, params["n_queries"])
        scale, codes = reader(train, params)
        k = params["k"]
        out = {"dataset": args.dataset, "dataset_sha256": digest, "k": k,
               "n_queries": len(test), "params_sha256": params_sha,
               "reader": {"scale": scale, "code64_seed": params["reader"]["code64_seed"]},
               "ceiling_recall_quantised": quantised_ceiling(train, test, truth, scale, k),
               "builds": [], "points": []}
        load_pgvector(conn, train)
        load_phasevec(conn, train, codes, params_sha)
        for build in range(1, params["builds"] + 1):
            for name, spec in params["sweeps"].items():
                engine, index = name.split(".")
                if engine == "pgvector":
                    secs, size = build_pgvector(conn, index, spec["build"])
                elif index == "find_ivf":
                    secs, size = build_phasevec_ivf(conn)
                else:
                    secs, size = 0.0, None      # find sweeps the readings: nothing to build
                out["builds"].append({"engine": engine, "index": index, "build": build,
                                      "seconds": secs, "bytes": size})
                for value, per_query in sweep(conn, engine, index, spec, test, truth, codes, k):
                    out["points"].append({"engine": engine, "index": index,
                                          "param_name": spec["param"], "param_value": value,
                                          "build": build, **summarize(per_query, k),
                                          "per_query": per_query})
    with open(args.out, "w") as f:
        json.dump(out, f)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
