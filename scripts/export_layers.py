#!/usr/bin/env python
"""Export the silver and gold tables from the DuckDB warehouse to CSV next to bronze/.

    DATA_DIR=data python scripts/export_layers.py
"""
import os
import sys

import duckdb

data_dir = os.path.abspath(os.environ.get("DATA_DIR", "data"))
db = os.path.join(data_dir, "warehouse.duckdb")
if not os.path.exists(db):
    sys.exit("warehouse not found at %s — run `make dbt` first" % db)

con = duckdb.connect(db, read_only=True)
for schema in ("silver", "gold"):
    out_dir = os.path.join(data_dir, schema)
    os.makedirs(out_dir, exist_ok=True)
    rels = con.execute(
        "select table_name from information_schema.tables where table_schema = ? order by 1", [schema]
    ).fetchall()
    for (name,) in rels:
        target = os.path.join(out_dir, name + ".csv")
        con.execute("copy (select * from %s.%s order by all) to '%s' (header, delimiter ',')" % (schema, name, target))
        n = con.execute("select count(*) from %s.%s" % (schema, name)).fetchone()[0]
        print("%-7s %-32s %7d rows -> %s" % (schema, name, n, os.path.relpath(target)))
