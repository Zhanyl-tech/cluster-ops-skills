PY ?= python3
VENV := .venv
BIN := $(VENV)/bin
# Exits non-zero unless the interpreter it runs under is 3.11 or newer.
PYCHECK := -c 'import sys; sys.exit(sys.version_info < (3, 11))'

.PHONY: help install list validate show index test lint typecheck check wheel-check clean

help: ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "};{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# Stock macOS python3 is 3.9, which cannot install this package. Check before
# creating anything, and throw away a venv an earlier failed attempt built with
# a too-old interpreter -- otherwise `make install PY=python3.12` would silently
# reuse it and fail the same way.
$(BIN)/cluster-ops-skills: pyproject.toml
	@$(PY) $(PYCHECK) 2>/dev/null || { \
		echo "cluster-ops-skills needs Python >= 3.11; '$(PY)' is $$($(PY) -V 2>&1 || echo missing)." >&2; \
		echo "Retry with a newer interpreter, e.g.: make install PY=python3.12" >&2; \
		exit 1; }
	@if [ -d $(VENV) ] && ! $(BIN)/python $(PYCHECK) 2>/dev/null; then \
		echo "Removing $(VENV): it was built with a Python older than 3.11 (or is broken)." >&2; \
		rm -rf $(VENV); fi
	@test -d $(VENV) || $(PY) -m venv $(VENV)
	@$(BIN)/python -m pip install -q --upgrade pip
	@$(BIN)/python -m pip install -q -e ".[dev]"
	@touch $(BIN)/cluster-ops-skills

install: $(BIN)/cluster-ops-skills ## Create the venv and install

list: install ## The skill index, as a model would see it
	@$(BIN)/cluster-ops-skills list

validate: install ## Check every skill against the contract and the claims ledger
	@$(BIN)/cluster-ops-skills validate

index: install ## Machine-readable index as JSON
	@$(BIN)/cluster-ops-skills index

test: install ## Run the test suite with the coverage floor CI uses
	@$(BIN)/python -m pytest -q --cov=cluster_ops_skills --cov-fail-under=90

lint: install ## ruff check + ruff format --check, exactly as CI runs them
	@$(BIN)/ruff check .
	@$(BIN)/ruff format --check .

typecheck: install ## mypy --strict
	@$(BIN)/mypy

check: lint typecheck test validate ## Everything the main CI job runs

wheel-check: install ## Build the wheel, install it in a throwaway venv, and validate from it
	@rm -rf dist build/wheel-venv
	@$(BIN)/python -m build --wheel --outdir dist -q
	@$(BIN)/python -m venv build/wheel-venv
	@build/wheel-venv/bin/python -m pip install -q dist/*.whl
	@cd build && wheel-venv/bin/cluster-ops-skills validate
	@cd build && wheel-venv/bin/cluster-ops-skills show queue-not-draining > /dev/null

clean: ## Remove venv, build output and caches
	@rm -rf $(VENV) dist build .pytest_cache .mypy_cache .ruff_cache .coverage
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
