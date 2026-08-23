PY ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: help install list validate show index test lint typecheck check clean

help: ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "};{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

$(BIN)/cluster-ops-skills: pyproject.toml
	@test -d $(VENV) || $(PY) -m venv $(VENV)
	@$(BIN)/python -m pip install -q --upgrade pip
	@$(BIN)/python -m pip install -q -e ".[dev]"
	@touch $(BIN)/cluster-ops-skills

install: $(BIN)/cluster-ops-skills ## Create the venv and install

list: install ## The skill index, as a model would see it
	@$(BIN)/cluster-ops-skills list

validate: install ## Check every skill against the contract
	@$(BIN)/cluster-ops-skills validate

index: install ## Machine-readable index as JSON
	@$(BIN)/cluster-ops-skills index

test: install ## Run the test suite
	@$(BIN)/python -m pytest -q

lint: install ## ruff check + ruff format --check, exactly as CI runs them
	@$(BIN)/ruff check .
	@$(BIN)/ruff format --check .

typecheck: install ## mypy --strict
	@$(BIN)/mypy

check: lint typecheck test validate ## Everything CI runs

clean: ## Remove venv and caches
	@rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
