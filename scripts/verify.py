import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.make_fixture import create  # noqa: E402


def run(*args, expected=0):
    command = [sys.executable, "-m", "warehouse", *map(str, args)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=600)
    receipt = {"command": command[1:], "returncode": result.returncode,
               "stdout": result.stdout, "stderr": result.stderr}
    if result.returncode != expected:
        raise RuntimeError(json.dumps(receipt))
    return receipt


def totals(rows):
    result = {}
    for row in rows:
        if not row["deleted"]:
            result[row["currency"]] = result.get(row["currency"], 0) + (
                row["quantity"] * row["unit_price_cents"])
    return result


def main():
    evidence = ROOT / "evidence"
    evidence.mkdir(exist_ok=True)
    receipts = []
    with tempfile.TemporaryDirectory(prefix="document-warehouse-") as temp:
        scratch = Path(temp)
        inputs = scratch / "inputs"
        expected = create(inputs, 20)
        first = scratch / "first"
        receipts.append(run("prepare", "--manifest", inputs / "manifest.json",
                            "--output", first, "--fixture-extraction"))
        receipts.append(run("build", "--run-dir", first))
        receipts.append(run("doctor", "--run-dir", first))
        observed = json.loads(receipts[-1]["stdout"])
        assert observed["lines"] == 80 and observed["raw_revisions"] == 80
        assert observed["spend_by_currency_cents"] == totals(expected)
        assert observed["build"]["models"] == 12 and observed["build"]["tests"] >= 20
        db = first / "warehouse.duckdb"
        source = inputs / "supplier-1.json"
        rows = json.loads(source.read_text(encoding="utf-8"))
        expected[20]["quantity"] += 2
        expected[20]["revision"] = 2
        expected[21]["deleted"] = True
        expected[21]["revision"] = 2
        rows[0] = expected[20]
        rows[1] = expected[21]
        source.write_text(json.dumps(rows), encoding="utf-8")
        second = scratch / "second"
        receipts.append(run("prepare", "--manifest", inputs / "manifest.json",
                            "--output", second, "--fixture-extraction"))
        receipts.append(run("build", "--run-dir", second, "--database", db))
        receipts.append(run("doctor", "--run-dir", second, "--database", db))
        updated = json.loads(receipts[-1]["stdout"])
        assert updated["lines"] == 79 and updated["raw_revisions"] == 82
        assert updated["spend_by_currency_cents"] == totals(expected)
        receipts.append(run("build", "--run-dir", second, "--database", db))
        receipts.append(run("doctor", "--run-dir", second, "--database", db))
        replayed = json.loads(receipts[-1]["stdout"])
        for field in ("lines", "currencies", "raw_revisions", "spend_by_currency_cents"):
            assert replayed[field] == updated[field]
        with duckdb.connect(str(db), read_only=True) as con:
            deleted = con.execute("select count(*) from main_intermediate.int_lines "
                                  "where deleted").fetchone()[0]
            assert deleted == 1
        shutil.copy2(second / "dbt-target/run_results.json", evidence / "dbt-run-results.json")
        shutil.copy2(second / "dbt-target/manifest.json", evidence / "dbt-manifest.json")
        proof = {"mode": "local-duckdb-fixture-extraction", "commands": receipts,
                 "initial": observed, "updated": updated,
                 "assertions": ["80 rows and currency totals",
                                f"12 models and {observed['build']['tests']} integrity tests",
                                "revision update", "tombstone delete", "idempotent replay"],
                 "scratch": str(scratch), "cleanup": False}
    assert not scratch.exists()
    proof["cleanup"] = True
    output = evidence / "verification.json"
    output.write_text(json.dumps(proof, indent=2), encoding="utf-8")
    assert output.exists()
    print(json.dumps({"receipt": str(output), "sha256": hashlib.sha256(
        output.read_bytes()).hexdigest(), "cleanup": True}))


if __name__ == "__main__":
    main()
