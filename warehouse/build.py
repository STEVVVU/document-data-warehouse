import json
import os
import subprocess
import sys
from pathlib import Path

import duckdb

from warehouse.domain import canonical, sha

ROOT = Path(__file__).resolve().parents[1]
RAW_TYPES = {
    "line_id": "VARCHAR", "invoice_id": "VARCHAR", "supplier_id": "VARCHAR",
    "supplier_name": "VARCHAR", "invoice_date": "DATE", "sku": "VARCHAR",
    "description": "VARCHAR", "category": "VARCHAR", "country": "VARCHAR",
    "currency": "VARCHAR", "quantity": "BIGINT", "unit_price_cents": "BIGINT",
    "revision": "BIGINT", "deleted": "BOOLEAN", "record_key": "VARCHAR",
    "supplier_key": "VARCHAR", "invoice_key": "VARCHAR", "product_key": "VARCHAR",
    "_data_source": "VARCHAR", "_load_time": "TIMESTAMP WITH TIME ZONE",
    "_content_hash": "VARCHAR",
}


def load_local(run_dir: Path, database: Path):
    prepared = json.loads((run_dir / "prepare.json").read_text(encoding="utf-8"))
    raw = run_dir / "raw.ndjson"
    if prepared["raw_sha256"] != sha(raw) or prepared["rejects"]:
        raise ValueError("raw batch integrity check failed")
    with duckdb.connect(str(database)) as con:
        con.execute("create schema if not exists raw")
        con.read_json(str(raw), columns=RAW_TYPES).create_view("incoming")
        if con.execute("select count(*) from incoming").fetchone()[0] != prepared["rows"]:
            raise ValueError("raw row count mismatch")
        con.begin()
        try:
            fields = ", ".join(f'"{name}" {kind} NOT NULL' for name, kind in RAW_TYPES.items())
            con.execute(f"create table if not exists raw.raw_lines ({fields}, "
                        "primary key(record_key, revision))")
            conflicts = con.execute("""
                select count(*) from incoming i join raw.raw_lines r
                using(record_key, revision) where i._content_hash <> r._content_hash
            """).fetchone()[0]
            if conflicts:
                raise ValueError("existing revision has conflicting payload; increment revision")
            con.execute("insert into raw.raw_lines select * from incoming on conflict do nothing")
            con.commit()
        except BaseException:
            con.rollback()
            raise


def build(run_dir: Path, *, database: Path | None = None, full_refresh=False,
          cloud=False, project=None, dataset=None, location="US"):
    run_dir = run_dir.resolve()
    database = (database or run_dir / "warehouse.duckdb").resolve()
    if cloud:
        from warehouse.cloud import validate_identifiers
        validate_identifiers(project, dataset)
    else:
        load_local(run_dir, database)
    profiles = run_dir / "profiles"
    profiles.mkdir(exist_ok=True)
    import yaml

    outputs = {"local": {"type": "duckdb", "path": str(database), "threads": 1}}
    if cloud:
        outputs["cloud"] = {
            "type": "bigquery", "method": "oauth", "project": project,
            "dataset": dataset + "_dbt", "location": location, "threads": 1,
            "job_execution_timeout_seconds": 300, "job_retries": 0,
            "maximum_bytes_billed": 100_000_000,
        }
    (profiles / "profiles.yml").write_text(yaml.safe_dump({
        "purchases": {"target": "cloud" if cloud else "local", "outputs": outputs}
    }), encoding="utf-8")
    vars_ = {"raw_schema": dataset if cloud else "raw"}
    if cloud:
        vars_["raw_database"] = project
    env = {**os.environ, "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
           "DBT_PROFILES_DIR": str(profiles), "DBT_LOG_PATH": str(run_dir / "dbt-logs")}
    command = [str(Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt")),
               "build", "--project-dir", str(ROOT), "--profiles-dir", str(profiles),
               "--target-path", str(run_dir / "dbt-target"), "--vars", json.dumps(vars_)]
    if full_refresh:
        command.append("--full-refresh")
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=600)
    (run_dir / "dbt-build.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"dbt build failed; see {run_dir / 'dbt-build.log'}")
    results_path = run_dir / "dbt-target" / "run_results.json"
    results = json.loads(results_path.read_text(encoding="utf-8"))
    bad = [r for r in results["results"] if r["status"] not in ("success", "pass")]
    if bad:
        raise RuntimeError("dbt returned a non-success model/test")
    report = {"mode": "live-bigquery" if cloud else "local-duckdb",
              "nodes": len(results["results"]),
              "models": sum(r["unique_id"].startswith("model.") for r in results["results"]),
              "tests": sum(r["unique_id"].startswith("test.") for r in results["results"]),
              "run_results_sha256": sha(results_path),
              "full_refresh": full_refresh}
    (run_dir / "build.json").write_text(canonical(report), encoding="utf-8")
    return report


def doctor(run_dir: Path, database: Path | None = None):
    database = database or run_dir / "warehouse.duckdb"
    with duckdb.connect(str(database), read_only=True) as con:
        result = dict(zip(("lines", "currencies"), con.execute("""
            select count(*), count(distinct currency)
            from main_marts.fct_invoice_lines
        """).fetchone()))
        result["spend_by_currency_cents"] = dict(con.execute("""
            select currency, sum(line_total_cents) from main_marts.fct_invoice_lines
            group by currency order by currency
        """).fetchall())
        result["raw_revisions"] = con.execute("select count(*) from raw.raw_lines").fetchone()[0]
    result["build"] = json.loads((run_dir / "build.json").read_text(encoding="utf-8"))
    if result["build"]["mode"] != "local-duckdb":
        raise ValueError("doctor currently verifies the local DuckDB target")
    return result
