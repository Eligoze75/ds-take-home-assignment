# dbt + DuckDB runtime. The repository is mounted at /app at run time, so model edits need no rebuild.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DBT_SEND_ANONYMOUS_USAGE_STATS=false

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY requirements-dbt.txt /tmp/requirements-dbt.txt
RUN pip install --no-cache-dir -r /tmp/requirements-dbt.txt

WORKDIR /app/dbt_project
ENTRYPOINT ["dbt"]
CMD ["build"]
