# Copyright 2026 Manuel Reyes Bravo
# SPDX-License-Identifier: Apache-2.0
"""Shared helpers: load results and claims, check a result against the schema, check a claim.

No third-party packages: a reviewer should be able to run every check with a bare python3.
The schema checker implements only the JSON Schema keywords results/schema.json uses.
"""
import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
SCHEMA = os.path.join(RESULTS, "schema.json")
CLAIMS = os.path.join(ROOT, "claims", "claims.json")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_dirs():
    """Every results/<benchmark>/<id>/ that holds a result.json, sorted."""
    out = []
    for bench in sorted(os.listdir(RESULTS)):
        bdir = os.path.join(RESULTS, bench)
        if not os.path.isdir(bdir):
            continue
        for rid in sorted(os.listdir(bdir)):
            if os.path.isfile(os.path.join(bdir, rid, "result.json")):
                out.append(os.path.join(bdir, rid))
    return out


# -- a small JSON Schema checker (type, const, enum, pattern, minLength, minimum, minItems,
#    required, properties, additionalProperties, items) ------------------------------------
_TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool,
    "integer": int, "number": (int, float), "null": type(None),
}


def _is(value, t):
    if t in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, _TYPES[t])


def check_schema(value, schema, where="$"):
    errs = []
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_is(value, x) for x in types):
            return [f"{where}: expected {t}, got {type(value).__name__}"]
    if "const" in schema and value != schema["const"]:
        errs.append(f"{where}: must be {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{where}: {value!r} not in {schema['enum']}")
    if isinstance(value, str):
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errs.append(f"{where}: {value!r} does not match {schema['pattern']}")
        if len(value) < schema.get("minLength", 0):
            errs.append(f"{where}: too short")
    if _is(value, "number") and "minimum" in schema and value < schema["minimum"]:
        errs.append(f"{where}: below {schema['minimum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errs.append(f"{where}: needs at least {schema['minItems']} items")
        if "items" in schema:
            for i, item in enumerate(value):
                errs += check_schema(item, schema["items"], f"{where}[{i}]")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errs.append(f"{where}: missing {key!r}")
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, sub in value.items():
            if key in props:
                errs += check_schema(sub, props[key], f"{where}.{key}")
            elif extra is False:
                errs.append(f"{where}: unexpected key {key!r}")
            elif isinstance(extra, dict):
                errs += check_schema(sub, extra, f"{where}.{key}")
    return errs


# -- claims ---------------------------------------------------------------------------------
TRANSFORMS = {
    None: lambda v: v,
    "round": lambda v: round(v),
    "round_thousands": lambda v: round(v / 1000),
}


def check_claim(claim, figures_by_run):
    """Return (ok, lines): every check of the claim, recomputed figure against stated value."""
    figures = figures_by_run.get(claim["run"])
    if figures is None:
        return False, [f"run {claim['run']} not found under results/"]
    ok, lines = True, []
    for c in claim["checks"]:
        if c["figure"] not in figures:
            ok = False
            lines.append(f"  MISSING {c['figure']}")
            continue
        raw = figures[c["figure"]]
        shown = TRANSFORMS[c.get("transform")](raw)
        good = shown == c["equals"]
        ok &= good
        how = f" ({c['transform']} of {raw})" if c.get("transform") else ""
        lines.append(f"  {'ok  ' if good else 'FAIL'} {c['figure']} = {shown!r}{how}; "
                     f"the claim says {c['equals']!r}")
    return ok, lines
