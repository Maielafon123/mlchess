PYTHON ?= python3

.PHONY: contract-generate contract-check contract-compat legacy-test

contract-generate:
	$(PYTHON) -m contracts.tooling.generate

contract-check:
	$(PYTHON) contracts/validate.py
	$(PYTHON) -m contracts.tooling.generate --check
	npm --prefix contracts run typecheck
	npm --prefix contracts test
	$(PYTHON) -m pytest backend/tests -q
	$(PYTHON) -m ruff check backend contracts
	$(PYTHON) -m ruff format --check backend contracts

contract-compat:
	$(PYTHON) -m contracts.tooling.compatibility --base-ref main

legacy-test:
	OMP_NUM_THREADS=1 $(PYTHON) -m pytest tests -q

.PHONY: backend-run
backend-run:
	$(PYTHON) -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log --no-server-header

.PHONY: release-preflight
release-preflight:
	$(PYTHON) -m infra.release_check
