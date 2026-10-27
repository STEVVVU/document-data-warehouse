---
name: verify-document-data-warehouse
description: Drive the document warehouse CLI, dbt transformations, integrity checks and incremental refresh with retained receipts.
---

# Status

Proved locally by evidence/verification.json, including durable state checks, replay, updates, deletion and cleanup. Live Gemini, GCS and BigQuery require authorized cloud execution separately. This implementation performs Python extraction outside dbt and does not require Dataproc for its SQL models.

## Launch

From the project root install requirements.lock.txt in .venv. Run `.venv/Scripts/python -m warehouse prepare --manifest fixtures/manifest.json --output .runs/verify --fixture-extraction` then `.venv/Scripts/python -m warehouse build --run-dir .runs/verify`. The build invokes real dbt and completes only after every model and data test succeeds. Each run owns its output directory.

## Doctor

Run `.venv/Scripts/python -m warehouse doctor --run-dir .runs/verify`. Confirm the fixture source hashes, exact raw row count, unique keys and dbt manifest/results agree. No credential or network check occurs in local mode.

## Drive

Use `scripts/verify.py` to launch an isolated run, invoke CLI commands, inspect durable results and test replay/rejection behavior. The mapped features are ingestion and transformations. Google SDK contract tests are separate and do not prove live GCP behavior.

## Evidence

`evidence/verification.json` retains CLI commands, return codes, assertions, artifact hashes and lifecycle outcomes. Evidence must survive deletion of its owned temporary directory. Capture rows and test results, not only dbt exit status.

## Cleanup

The verification script owns its tempfile directory and removes it through Python TemporaryDirectory. It starts no daemon. Never delete source, the environment, dependencies or evidence. Never recursively delete a path derived from an untrusted manifest.

## Helpers

`.venv/Scripts/python scripts/verify.py` drives the lifecycle. `.venv/Scripts/python scripts/benchmark.py` retains repeated end-to-end benchmark receipts and output checks.
