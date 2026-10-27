# Document data warehouse

Python integration code lives in warehouse/. dbt SQL models live in models/staging/, models/intermediate/, models/marts/. Tests live in tests/. No live credentials or generated warehouse state belong in Git.

Use .venv/Scripts/python for Python and .venv/Scripts/dbt for dbt. Install requirements.lock.txt after it is generated. Run `python -m pytest`, `python -m ruff check .`, and the maintained verification skill at .agents/skills/verify-document-data-warehouse/SKILL.md. Evidence belongs in evidence/, mutable runtime data in .runs/.

Cloud writes require explicit --cloud and project/bucket/dataset parameters. Local DuckDB measurements never support GCP throughput claims. Preserve provenance, exact integer cents, rejection evidence and actual cloud job receipts.
