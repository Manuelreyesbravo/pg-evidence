# Submit your run

A number claims; the machine decides. You do not type a figure anywhere: you add raw files,
and CI computes the figures from them.

## 1. Run a benchmark

- **agent-gate-compare**: fork [agent-gate-demo](https://github.com/Manuelreyesbravo/agent-gate-demo),
  then from a clone of this repository:

  ```sh
  make rerun-agent-gate-compare FORK=you/agent-gate-demo     # config=cited by default
  ```

  It dispatches the `compare` workflow on your fork, waits, downloads the artifact
  `compare-results-cited` (compare-results.json, run-metadata.json, SHA256SUMS) and runs
  `tools/ingest.py`. Already have a run? `gh run download <id> -n compare-results-cited -D dir`
  and `python3 tools/ingest.py agent-gate-compare dir --by "Your Name" --date YYYY-MM-DD`.

- **image-preflight**: `make rerun-image-preflight` (needs the preflight binary).

- **phasevec-recall**: not open for submissions until the first reference run exists.

## 2. Check it locally

```sh
make validate site
```

`tools/ingest.py` has written `results/<benchmark>/<id>/result.json` with
`"status": "submitted"`, your raw files and their sha256. Fill in what the run did not
record and you know (for example `hardware.cpu` on your own machine); leave `null` what
you do not know.

## 3. Open a pull request

Add the new `results/<benchmark>/<id>/` directory and the regenerated `site/`. Nothing
else. CI (`validate` workflow) then:

1. checks `result.json` against `results/schema.json`;
2. checks that every raw file has the sha256 the result records;
3. recomputes every figure from the raw files and fails on any stored figure that differs;
4. requires every run added by the PR to be `"submitted"`;
5. rechecks every published claim, and that `site/` is what the data renders.

A run whose numbers disagree with a cited claim is welcome: it is merged and shown next to
the cited run. If it shows the claim does not hold, the claim is corrected or withdrawn,
not your run.

## What a maintainer does

- Promotes a run to `"cited"` only when a published sentence will point at it, in the same
  commit that adds or changes that sentence in `claims/claims.json`.
- Never edits a raw file. A wrong raw file is replaced by a new run with a new id.
