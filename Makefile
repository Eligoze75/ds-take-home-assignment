# One entrypoint for everything. DATA_DIR selects the dataset (bronze CSVs in, warehouse + exports out).
# dbt runs in Docker (docker-compose.yml); the *-local targets run it from the venv instead.
DATA_DIR ?= $(CURDIR)/data
export DATA_DIR

VENV := $(CURDIR)/.venv
PY   := $(VENV)/bin/python
DBT  := $(VENV)/bin/dbt
DC   := docker compose
RUN  := $(DC) run --rm

.PHONY: setup image venv dbt deps test export data clean all package release dbt-local test-local export-local data-local report

setup: image venv

image:
	$(DC) build

venv:
	python3 -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements.txt

# ---- dbt in Docker -------------------------------------------------------------------------
# dbt packages (dbt_utils) are vendored in dbt_project/dbt_packages, so nothing here needs the network.
dbt:
	$(RUN) dbt build

deps:            # refresh the vendored packages (network)
	$(RUN) dbt deps

test:
	$(RUN) dbt test

export:
	$(RUN) --entrypoint python dbt /app/scripts/export_layers.py

data: dbt export

# ---- dbt from the venv (no Docker) ----------------------------------------------------------
dbt-local:
	cd dbt_project && $(DBT) build

test-local:
	cd dbt_project && $(DBT) test

export-local:
	$(PY) scripts/export_layers.py

data-local: dbt-local export-local

# ---------------------------------------------------------------------------------------------
clean:
	rm -rf dbt_project/target dbt_project/logs $(DATA_DIR)/warehouse.duckdb $(DATA_DIR)/silver $(DATA_DIR)/gold

# Candidates: extend `all` so it regenerates everything your write-up cites into outputs/.
all: data

# Company A timing note. PDF lands in outputs/ via report/_quarto.yml.
report:
	QUARTO_PYTHON=$(CURDIR)/remarcable_env/bin/python quarto render report/when_to_buy.qmd

# Candidate zip: everything except internal/, environments, build artefacts and OS litter (dbt_packages stay: vendored). Fails if anything internal slips in.
PACKAGE := dsci_take_home_v7.zip
package:
	rm -f $(PACKAGE)
	zip -qr $(PACKAGE) . -x 'internal/*' '.venv/*' '*/__pycache__/*' 'outputs/*' '*.duckdb' '*.duckdb.wal' \
	    'dbt_project/target/*' 'dbt_project/logs/*' '.git/*' '*.DS_Store' 'PLAN.md' '$(PACKAGE)'
	@if unzip -l $(PACKAGE) | grep -qE ' internal/| \.DS_Store| PLAN\.md|warehouse\.duckdb'; then echo "PACKAGE CONTAINS INTERNAL FILES"; unzip -l $(PACKAGE) | grep -E 'internal/|DS_Store|PLAN|duckdb'; rm -f $(PACKAGE); exit 1; fi
	@echo "packaged $(PACKAGE): $$(unzip -l $(PACKAGE) | tail -1)"

# Derived folders: ../v7-candidate (what we send) and ../v7-solution (the complete example submission).
release:
	$(PY) internal/build_release.py
