# pg-evidence: one target per published number, and the checks that keep them honest.
# Needs only python3 (and gh / preflight / PostgreSQL for the reruns).

PY ?= python3
CLAIMS := $(shell $(PY) -c "import json;print(' '.join(c['id'] for c in json.load(open('claims/claims.json'))['claims']))")

.PHONY: help validate site check claims $(addprefix claim-,$(CLAIMS)) \
        rerun-agent-gate-compare rerun-image-preflight recall-phasevec

help:
	@echo "make validate                 schema + sha256 + figures recomputed + every claim"
	@echo "make site                     render site/ from results/ and claims/"
	@echo "make check                    validate, and fail if site/ is stale (what CI runs)"
	@echo "make claims                   recompute every published claim, step by step"
	@$(foreach c,$(CLAIMS),echo "make claim-$(c)";)
	@echo "make rerun-agent-gate-compare FORK=you/agent-gate-demo   rerun the cited MCP comparison in CI"
	@echo "make rerun-image-preflight    rerun Red Hat preflight on the cited image (needs preflight)"
	@echo "make recall-phasevec DSN=...  pg_phasevec vs pgvector recall (designed; see its SPEC.md)"

validate:
	$(PY) tools/validate.py

site:
	$(PY) tools/build_site.py

check: validate site
	git diff --exit-code -- site || { echo "site/ is stale: run make site and commit it"; exit 1; }

claims: $(addprefix claim-,$(CLAIMS))

# One target per published number: recompute it from the raw data of the run it cites.
$(addprefix claim-,$(CLAIMS)): claim-%:
	$(PY) tools/claim.py $*

rerun-agent-gate-compare:
	benchmarks/agent-gate-compare/rerun.sh $(FORK)

rerun-image-preflight:
	benchmarks/image-preflight/rerun.sh

recall-phasevec:
	$(PY) benchmarks/phasevec-recall/run_recall.py --dsn "$(DSN)" --dataset "$(or $(DATASET),nytimes-256-angular)"
