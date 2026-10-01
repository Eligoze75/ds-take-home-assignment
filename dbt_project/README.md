# procurement\_lakehouse (dbt)

Builds the silver and gold layers of the procurement lakehouse from the bronze CSV files in `$DATA_DIR/bronze/` using DuckDB. Nothing to provision, no credentials.

```
models/
  silver/           one table per bronze table: ids, dates, amounts and status normalised
  gold/             dim_item, dim_vendor, dim_customer, fct_purchase_order_line,
                    item_purchase_history (legacy aggregate feeding the dashboards)
macros/             parsing helpers, schema naming
```

## Run

From the repository root, in Docker (recommended):

```sh
make setup      # docker compose build + python venv
make dbt        # dbt build (models + tests) into data/warehouse.duckdb
make data       # dbt build, then export silver/ and gold/ as CSV next to bronze/
make test       # dbt test only
```

&nbsp;

Any dbt command: `docker compose run --rm dbt <command>`, e.g. `docker compose run --rm dbt run --select gold`.

&nbsp;

Without Docker, from this folder with dbt-duckdb installed (`make data-local` does the same):

```sh
dbt build
```

&nbsp;

`dbt_packages/` (dbt\_utils) is vendored, so no `dbt deps` is needed; `make deps` refreshes it.

&nbsp;

`DATA_DIR` selects the dataset: the bronze files are read from `$DATA_DIR/bronze/` and the warehouse is written to `$DATA_DIR/warehouse.duckdb`. In Docker the default is `/app/data`, the repo's `data/` folder through the single repo mount. Point `DATA_DIR` at a directory outside the repo and `make` mounts that path at `/data` instead. Locally it defaults to `../data` relative to this folder.

## Notes

- The project is provided as-is. Modify it, extend it, add models and tests: whatever best supports your work. Any gold table you rely on for your analysis should be a model here.  
- Sources are read straight from CSV with every column as text; the silver models own the casts.