import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.make_fixture import create  # noqa: E402
from scripts.verify import run, totals  # noqa: E402


def source_hashes():
    return {str(path.relative_to(ROOT)).replace("\\", "/"):
            hashlib.sha256(path.read_bytes()).hexdigest()
            for folder in ("warehouse", "models", "data_tests", "scripts")
            for path in sorted((ROOT / folder).rglob("*"))
            if path.suffix in (".py", ".sql", ".yml")}


def main():
    evidence = ROOT / "evidence"
    evidence.mkdir(exist_ok=True)
    output = evidence / "benchmark.json"
    if output.exists():
        raise RuntimeError("benchmark receipt exists; preserve it before another campaign")
    artifacts = evidence / ("dbt-campaign-" +
                            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    artifacts.mkdir()
    receipt = {
        "claim": "Compare local full and incremental refresh with identical raw revisions and "
                 "verify per-currency outputs. No GCP performance claim.",
        "clock": "time.perf_counter, seconds, CLI start through all dbt tests completion",
        "host": {"platform": platform.platform(), "python": sys.version,
                 "logical_cpus": os.cpu_count(), "ram_bytes": psutil.virtual_memory().total,
                 "available_ram_start": psutil.virtual_memory().available,
                 "cpu_percent_start": psutil.cpu_percent(interval=0.2)},
        "versions": subprocess.check_output([sys.executable, "-m", "pip", "freeze"],
                                             text=True).splitlines(),
        "source_sha256": source_hashes(), "runs": [], "cleanup": False,
    }
    try:
        with tempfile.TemporaryDirectory(prefix="warehouse-benchmark-") as temp:
            scratch = Path(temp)
            for scale in (1000, 10000):
                inputs = scratch / f"inputs-{scale}"
                expected = create(inputs, scale, documents=False)
                base = scratch / f"base-{scale}"
                run("prepare", "--manifest", inputs / "manifest.json", "--output", base)
                run("build", "--run-dir", base)
                revised_expected = []
                for source in json.loads((inputs / "manifest.json").read_text())["sources"]:
                    path = inputs / source["path"]
                    if path.suffix == ".csv":
                        import csv
                        with path.open(newline="", encoding="utf-8") as handle:
                            rows = list(csv.DictReader(handle))
                        from warehouse.domain import Line
                        rows = [Line.model_validate(row).model_dump(mode="json") for row in rows]
                    else:
                        rows = json.loads(path.read_text(encoding="utf-8"))
                    for i, row in enumerate(rows):
                        if i % 10 == 0:
                            row["quantity"] += 1
                            row["revision"] = 2
                        elif i % 100 == 1:
                            row["deleted"] = True
                            row["revision"] = 2
                    revised_expected.extend(rows)
                    path.write_text(json.dumps(rows), encoding="utf-8")
                    source["kind"] = "json"
                manifest = json.loads((inputs / "manifest.json").read_text())
                for source in manifest["sources"]:
                    source["kind"] = "json"
                (inputs / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                prepared = scratch / f"prepared-{scale}"
                run("prepare", "--manifest", inputs / "manifest.json", "--output", prepared)
                oracle = totals(revised_expected)
                oracle_count = sum(not row["deleted"] for row in revised_expected)
                assert len(expected) == 4 * scale
                for repeat in range(5):
                    sides = ("full", "incremental") if repeat % 2 == 0 else ("incremental", "full")
                    for side in sides:
                        work = scratch / f"{scale}-{repeat}-{side}"
                        work.mkdir()
                        for name in ("raw.ndjson", "prepare.json"):
                            shutil.copy2(prepared / name, work / name)
                        database = work / "warehouse.duckdb"
                        shutil.copy2(base / "warehouse.duckdb", database)
                        args = ["build", "--run-dir", work]
                        if side == "full":
                            args.append("--full-refresh")
                        start = time.perf_counter()
                        result = run(*args)
                        elapsed = time.perf_counter() - start
                        observed = json.loads(run("doctor", "--run-dir", work)["stdout"])
                        assert observed["spend_by_currency_cents"] == oracle
                        assert observed["lines"] == oracle_count
                        assert observed["raw_revisions"] == 4 * scale + 4 * (
                            scale // 10 + scale // 100)
                        receipt["runs"].append({
                            "base_lines": 4 * scale, "side": side, "repeat": repeat,
                            "elapsed_seconds": elapsed, "returncode": result["returncode"],
                            "observed": observed, "oracle_totals": oracle,
                            "oracle_lines": oracle_count, "output_checks_passed": True,
                        })
                        output.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
                        print(f"{4 * scale} lines {side} repeat={repeat} {elapsed:.3f}s",
                              flush=True)
                        shutil.copy2(work / "dbt-target/run_results.json",
                                     artifacts / f"dbt-{scale}-{repeat}-{side}.json")
            receipt["summary"] = []
            for scale in (4000, 40000):
                for side in ("full", "incremental"):
                    values = [r["elapsed_seconds"] for r in receipt["runs"]
                              if r["base_lines"] == scale and r["side"] == side]
                    receipt["summary"].append({"base_lines": scale, "side": side,
                        "repeats": len(values), "median_seconds": statistics.median(values),
                        "min_seconds": min(values), "max_seconds": max(values)})
        assert not scratch.exists()
        receipt["cleanup"] = True
    except BaseException as error:
        receipt["failure"] = str(error)
        raise
    finally:
        output.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt["summary"], indent=2))


if __name__ == "__main__":
    main()
