# Transformations

## Sub-features

dbt staging, latest-record selection, ten business marts, uniqueness/null/relationship tests, full and incremental refresh.

## How to get to it (user POV)

Run `python -m warehouse build --run-dir .runs/demo` after ingestion.

## Driving it with CLI

Run scripts/verify.py. Inspect dbt run_results, query line counts and money totals, mutate an input revision, rebuild and compare to an independent expected total. Replaying the revision must not add duplicate lines.

## Gotchas

DuckDB local dbt is a real execution target; it does not validate BigQuery dialect, Gemini responses, credentials or Dataproc execution. These require separate receipts.
