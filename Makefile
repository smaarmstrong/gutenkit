# gutenkit — standard-library-only CLI; the Makefile just wraps the common
# chores. No third-party tools required.

PYTHON ?= python3
BASH_COMPLETION_DIR ?= $(HOME)/.local/share/bash-completion/completions

MODULES := gutenkit/*.py gutenkit/providers/*.py

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-14s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install as an editable user package (puts `gutenkit` on PATH)
	$(PYTHON) -m pip install --user -e .

.PHONY: check
check: ## Byte-compile every module (fast syntax check, no deps)
	$(PYTHON) -m py_compile $(MODULES)
	@echo "ok: all modules compile"

.PHONY: test
test: check ## Offline smoke test: version + source listing
	$(PYTHON) -m gutenkit --version
	$(PYTHON) -m gutenkit sources

.PHONY: smoke
smoke: ## Networked smoke test: one search per source (needs Perseus index)
	$(PYTHON) -m gutenkit search "pride and prejudice" --source gutenberg,standardebooks --limit 2
	-$(PYTHON) -m gutenkit search homer --source perseus --limit 2

.PHONY: index
index: ## Build the one-time Perseus catalogue (~130 MB streamed, cached)
	$(PYTHON) -m gutenkit index perseus

.PHONY: completions
completions: ## Install bash completion for the current user
	@mkdir -p $(BASH_COMPLETION_DIR)
	cp completions/gutenkit.bash $(BASH_COMPLETION_DIR)/gutenkit
	@echo "installed to $(BASH_COMPLETION_DIR)/gutenkit (start a new shell)"

.PHONY: clean
clean: ## Remove caches and build artefacts
	rm -rf build dist *.egg-info gutenkit/*.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
