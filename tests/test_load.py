import json

import duckdb
import pytest

from scripts.make_fixture import create
from warehouse.build import load_local
from warehouse.ingest import prepare


def test_replay_and_conflicting_existing_revision_rollback(tmp_path):
    create(tmp_path / "inputs", 2)
    prepare(tmp_path / "inputs/manifest.json", tmp_path / "first", True)
    db = tmp_path / "local.duckdb"
    load_local(tmp_path / "first", db)
    load_local(tmp_path / "first", db)
    with duckdb.connect(str(db)) as con:
        assert con.execute("select count(*) from raw.raw_lines").fetchone()[0] == 8
    source = tmp_path / "inputs/supplier-1.json"
    rows = json.loads(source.read_text())
    rows[0]["quantity"] += 1
    source.write_text(json.dumps(rows))
    prepare(tmp_path / "inputs/manifest.json", tmp_path / "second", True)
    with pytest.raises(ValueError, match="conflicting payload"):
        load_local(tmp_path / "second", db)
    with duckdb.connect(str(db)) as con:
        assert con.execute("select count(*) from raw.raw_lines").fetchone()[0] == 8
