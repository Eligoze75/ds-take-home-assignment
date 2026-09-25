# Remarcable — Data Scientist Take-Home

**Estimated effort:** 4-6 hours. **Submit within:** 5 business days. **Stack:** Python 3.10+ (pandas or polars); dbt with DuckDB, provided and run in Docker (nothing to provision, no credentials).

---

## Context

Remarcable builds procurement, tools and warehouse management software for trade contractors. Our data platform is a multi-tenant lakehouse: every customer's purchasing flows through the same tables, tagged with a `customer_id`.

| Layer | What it is | Where |
| :---- | :---- | :---- |
| **Bronze** | Raw, append-only extracts from the source systems, as CSV | `data/bronze/` |
| **Silver** | Typed, conformed tables built by dbt from bronze | `data/silver/` (export), `dbt_project/models/silver/` |
| **Gold** | Star schema for reporting: `dim_*`, `fct_*`, plus the legacy `item_purchase_history` aggregate that feeds today's dashboards | `data/gold/` (export), `dbt_project/models/gold/` |

The dbt project builds and its tests pass. It is yours to use, extend, or restructure; any gold table your analysis relies on must be a dbt model in this project.

**Company A** (`CUST-A`) is one of our customers, an electrical contractor who buys a set of common items repeatedly across many projects.

---

## Setup

Requires Docker (Desktop or Engine with Compose) and Python 3.10+. After `make setup`, nothing needs the network.

```sh
make setup      # builds the dbt image and creates a Python venv with the analysis dependencies
make data       # dbt build (silver + gold + tests) in Docker into data/warehouse.duckdb, then export CSVs
```

dbt runs inside a container defined by `Dockerfile` / `docker-compose.yml`; the repository is mounted, so editing a model and re-running `make data` needs no rebuild. `make dbt`, `make test` and `make export` are the individual steps. If you cannot run Docker, `make data-local` does the same with dbt installed in the venv.

`make data` regenerates `data/silver/` and `data/gold/` from `data/bronze/`. Both exports are included so you can start in pandas immediately; the warehouse file is the same data in DuckDB.

`make all` currently just runs `make data` — extend it so that it also regenerates everything your write-up cites. See *Reproducibility* below.

`DATA_DIR` selects the dataset (default `data/`).

---

## Data dictionary

**bronze / silver `purchase_orders`** — one row per PO header

| column | description |
| :---- | :---- |
| `po_number` | PO identifier, e.g. `PO-100123` |
| `customer_id` | the Remarcable customer (tenant) that issued the PO |
| `vendor_id`, `vendor_name` | the vendor the PO was sent to |
| `order_date` |  |
| `status` | `Open`, `Received`, `Closed`, `Cancelled` |
| `total_amount` | PO total as recorded by the source system |

**bronze / silver `itemized_purchase_orders`** — PO lines

| column | description |
| :---- | :---- |
| `po_number` |  |
| `customer_id` | customer recorded on the line by the source system |
| `item_id` |  |
| `quantity_ordered` |  |
| `unit_price_paid` | unit price on the line, in the item's unit of measure |

**bronze / silver `items`** — item master

| column | description |
| :---- | :---- |
| `item_id`, `description`, `category` |  |
| `unit_of_measure` | `EA` each, `RL` reel, `BX` box, `BG` bag, `PK` pack |
| `manufacturer_id`, `manufacturer_name` |  |

**bronze / silver `item_pricing`** — vendor list price on file, independent of any purchase. Vendors refresh their price files about weekly, so each (item, vendor) has a series of snapshots.

| column | description |
| :---- | :---- |
| `item_id`, `vendor_id` |  |
| `price_effective_date` | date the snapshot took effect |
| `vendor_price` | list price on that date |

**gold** — `dim_item`, `dim_vendor`, `dim_customer`, `fct_purchase_order_line` (documented as one row per PO line, with header attributes attached), `item_purchase_history` (legacy: one row per item with purchase frequency, first/last purchase date and p25/p50/p75/p90 of unit price paid). Column-level descriptions are in `dbt_project/models/gold/_gold.yml`.

**`data/search_queries.csv`** — 40 free-text queries for evaluating Task 2\. `query_id` identifies each one. `query_type` groups them (exact, misspelling, abbreviation, partial, word order, and queries with no good match). `expected_item_ids` holds the item ids a good search should return, pipe-separated, and is empty where nothing in the catalog is a good answer. `notes` says in a line what each query is testing.

---

## Task 1 — Company A: when to buy, and what price to expect *(3-4 hours)*

Company A asked us two things:

> (a) "Is there a time of year when we get the best prices on the items we buy most often, and what should we be thinking about when we decide what to purchase when?"

> (b) "Before we issue a Purchase Order, can you tell us what unit price to expect?"

You have three views into price: the vendor's list price over time (`item_pricing`), what was actually paid (`itemized_purchase_orders`), and the legacy per-item aggregate (`item_purchase_history`).

**Deliverables**

1. **Recommendation for Company A** — one page or less, written for a procurement manager, with 2–3 charts that support it. Say what they should do, what it is worth, and what you are not sure about.  
2. **Price expectation model** — predict `unit_price_paid` for a (customer, item, vendor, quantity, order date). Compare at least three approaches, one of them a simple baseline, on a holdout that reflects how the model would actually be used. Report the metrics you think matter and explain why the approaches rank the way they do.  
3. **Explanation** — one global view of what drives the prediction and one local explanation for a single PO line. Use SHAP if your model is tree-based; coefficients or a shallow decision tree are fine otherwise.  
4. **Gold table(s)** behind 1–3 as dbt models, shaped so one of them could power a customer-facing price report in the platform.

---

## Task 2 — Item search *(1-2 hours)*

Build a function that takes a free-text query and returns a ranked list of catalog items (`item_id`, `description`, relevance score at minimum). Users type things like `12 awg thhn blk`, `emt 1/2 conduit`, `gfci 20a`, or misspell and abbreviate freely.

**Deliverables**

1. The search code and a short explanation of the approach and why you chose it for this catalog.  
2. An evaluation on `data/search_queries.csv` **and** on queries of your own, with the metrics you think fit the problem. Say what your approach gets right/wrong and what would break at the scale of 50,000 items.

---

## Decisions we will discuss

Each task has three decisions we care about more than the final numbers. Document how you decided, and what you rejected. We will ask about them in the follow-up interview.

|  | Decision |
| :---- | :---- |
| 1.1 | How you defined "the items we buy most often", and how you framed the prediction target and the train/test split |
| 1.2 | How you decided whether a time-of-year effect is real, and how that shaped the recommendation and its caveats |
| 1.3 | Why the models rank the way they do, and what the explanation says about the drivers of price |
| 2.1 | How you handled abbreviations, units and synonyms in queries and descriptions |
| 2.2 | Why this ranking technique for a catalog of this size |
| 2.3 | How you evaluated, what you tested beyond our query set, and how it would scale |

---

## Reproducibility

We will grade this. From a clean clone of your submission, on our machine:

```sh
make setup
make all
```

must produce everything your write-up cites (tables, charts, metrics) under `outputs/`. We will then run it again with `DATA_DIR` pointing at a second dataset with the same schema and file layout. Pin your dependencies; do not rely on absolute paths or on notebook cells run by hand. A notebook is welcome as a narrative, but the numbers in it must come from the pipeline.

---

## Using AI assistants

Use whatever tools you normally use; we do not score that. In the follow-up we will ask you to walk through parts of your submission and explain why a particular line does what it does, so make sure you can stand behind everything you send.

---

## Deliverables checklist

- [ ] Git repository (link or zip) containing the dbt project, your code, `outputs/`, and any changes to the Docker setup  
- [ ] `README.md`: how to run, assumptions, data-handling decisions, and the six decisions above  
- [ ] Task 1: recommendation (≤ 1 page, 2–3 charts), model comparison, global \+ local explanation, gold dbt model(s)  
- [ ] Task 2: search code, approach, evaluation on the shipped queries and your own  
- [ ] `make setup && make all` works from a clean clone and honours `DATA_DIR`

&nbsp;

We would rather see clean, readable, documented code than exhaustive coverage of every edge case.

---

## Evaluation criteria

| Area | What we look for |
| :---- | :---- |
| **Data handling** | How do you work with the data given, and where does that logic live? |
| **Code quality** | Readable, modular, reasonably tested; would a teammate understand this in six months? |
| **Analytical depth & judgment** | A defensible recommendation, with the caveats called out |
| **Modeling rigor** | Honest evaluation: baseline, appropriate holdout, metrics that fit the use |
| **Explainability** | Can you say what the model learned, and check whether it is plausible? |
| **Search relevance** | Thoughtful, justified choice of technique, evaluated rather than asserted |
| **Communication** | Clear findings, prioritised for a non-technical stakeholder |
| **Judgment under ambiguity** | Where the brief was open-ended, did you make and articulate reasonable decisions? |
| **Reproducibility** | One command, clean clone |

&nbsp;
