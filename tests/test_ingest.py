import json
from unittest.mock import Mock

import pytest

from scripts.make_fixture import create
from warehouse.domain import Line, confined
from warehouse.ingest import extract_gemini, prepare


def test_fixture_provenance_and_exact_totals(tmp_path):
    expected = create(tmp_path / "inputs", 20)
    report = prepare(tmp_path / "inputs/manifest.json", tmp_path / "run", True)
    rows = [json.loads(line) for line in (tmp_path / "run/raw.ndjson").read_text().splitlines()]
    assert report["rows"] == len(expected) == 80 and not report["cloud_extraction"]
    assert sum(r["quantity"] * r["unit_price_cents"] for r in rows) == sum(
        r["quantity"] * r["unit_price_cents"] for r in expected)
    assert len({r["record_key"] for r in rows}) == 80
    assert all(r["_data_source"] and r["_load_time"] and r["_content_hash"] for r in rows)
    assert report["sources"][3]["extraction"] == "fixture"


@pytest.mark.parametrize("bad", [True, 1.5, "1.0", "1e3", -1, 0])
def test_quantity_rejects_inexact_and_nonpositive(tmp_path, bad):
    row = create(tmp_path, 1)[0]
    row["quantity"] = bad
    with pytest.raises(ValueError):
        Line.model_validate(row)


def test_invalid_batch_is_not_published_and_paths_confined(tmp_path):
    create(tmp_path / "inputs", 2)
    source = tmp_path / "inputs/supplier-1.json"
    rows = json.loads(source.read_text())
    rows[0]["currency"] = "invalid"
    source.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match="invalid rows"):
        prepare(tmp_path / "inputs/manifest.json", tmp_path / "run", True)
    assert not (tmp_path / "run/raw.ndjson").exists()
    assert (tmp_path / "run/rejects.ndjson").stat().st_size > 0
    with pytest.raises(ValueError, match="inside"):
        confined(tmp_path / "inputs", "../run/rejects.ndjson")


@pytest.mark.parametrize("bad", [0, True, "2024-01-01T00:00:00Z", "20240101", "2024-02-30"])
def test_date_requires_exact_iso_calendar_date(tmp_path, bad):
    row = create(tmp_path, 1)[0]
    row["invoice_date"] = bad
    with pytest.raises(ValueError):
        Line.model_validate(row)


def test_conflicting_revision_rejected_exact_duplicate_collapses(tmp_path):
    create(tmp_path / "inputs", 2)
    source = tmp_path / "inputs/supplier-1.json"
    rows = json.loads(source.read_text())
    rows.append(rows[0].copy())
    source.write_text(json.dumps(rows))
    report = prepare(tmp_path / "inputs/manifest.json", tmp_path / "first", True)
    assert report["rows"] == 8
    rows[-1]["quantity"] += 1
    source.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match="invalid rows"):
        prepare(tmp_path / "inputs/manifest.json", tmp_path / "second", True)


def test_gemini_structured_contract(tmp_path):
    rows = create(tmp_path / "inputs", 1)
    client = Mock()
    client.models.generate_content.return_value.text = json.dumps({"lines": rows[:1]})
    path = tmp_path / "inputs/invoice.txt"
    result = extract_gemini(path, "text/plain", "explicit-model", "demo-project", "US", client)
    assert result[0]["line_id"] == rows[0]["line_id"]
    call = client.models.generate_content.call_args.kwargs
    assert call["model"] == "explicit-model"
    assert call["config"].response_mime_type == "application/json"
    assert call["contents"][0].inline_data.data == path.read_bytes()
    client.models.generate_content.return_value.text = '{"lines":[]}'
    with pytest.raises(ValueError):
        extract_gemini(path, "text/plain", "explicit-model", "demo-project", "US", client)
