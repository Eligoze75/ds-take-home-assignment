# One entrypoint for everything. DATA_DIR selects the dataset (bronze CSVs in, warehouse + exports out).
# dbt runs in Docker (docker-compose.yml); the *-local targets run it from the venv instead.
DATA_DIR ?= $(CURDIR)/data
MODELS_DIR ?= $(CURDIR)/outputs/models
export DATA_DIR
export MODELS_DIR

VENV := $(CURDIR)/.venv
PY   := $(VENV)/bin/python
DBT  := $(VENV)/bin/dbt
JUPYTER := $(VENV)/bin/jupyter
TOOLS := $(CURDIR)/.tools
QUARTO := $(TOOLS)/quarto/bin/quarto
DC   := docker compose
RUN  := $(DC) run --rm
# Local Quarto and TinyTeX from `make setup`. The venv python executes the report code.
quarto_render = texbin="$$(ls -d $(TOOLS)/TinyTeX/bin/*/ 2>/dev/null | head -1)"; \
	if [ -f "$(TOOLS)/fonts.conf" ]; then export FONTCONFIG_FILE="$(TOOLS)/fonts.conf"; fi; \
	PATH="$(TOOLS)/quarto/bin:$${texbin}:$$PATH" QUARTO_PYTHON=$(PY) $(QUARTO) render

.PHONY: setup image venv tools dbt deps test export data clean all package release dbt-local test-local export-local data-local models report report-price report-search

setup: image venv tools

tools: venv
	bash scripts/install_tools.sh

image:
	$(DC) build

venv:
	@PYTHON_BIN="$$(bash scripts/ensure_python.sh)"; \
	test -n "$$PYTHON_BIN" || { echo "error: could not find or install Python 3.12+"; exit 1; }; \
	echo "using $$PYTHON_BIN for $(VENV)"; \
	"$$PYTHON_BIN" -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements.txt
	$(PY) -m pip install -q --no-deps shap==0.52.0
	$(PY) -m ipykernel install --sys-prefix --name=ds-take-home --display-name="ds-take-home"

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

# Warehouse, trained models, then every Quarto report. PDFs land in outputs/.
all: report report-price report-search

# Fits the single regressor and TreeHouse. Does not rewrite the notebook.
# The kernel cwd is notebooks/, and MODELS_DIR is absolute, so the dumps land in outputs/models/.
models: data
	mkdir -p "$(MODELS_DIR)"
	PATH="$(VENV)/bin:$$PATH" $(JUPYTER) execute --timeout=-1 --kernel_name=python3 notebooks/model_training.ipynb

# PDFs for report/*.qmd land in outputs/ via report/_quarto.yml.
report: data
	$(quarto_render) report/when_to_buy.qmd

# Holdout score and one explained quote. Loads the saved regressor, then refits TreeHouse.
report-price: models
	$(quarto_render) report/price_quotes.qmd

# Search evals. PDF lands in outputs/ via evals_documentation/_quarto.yml.
report-search: data
	$(quarto_render) evals_documentation/item_search_evals.qmd

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
