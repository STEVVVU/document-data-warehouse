import json
from unittest.mock import Mock

import pytest

from scripts.make_fixture import create
from warehouse.cloud import upload_batch
from warehouse.ingest import prepare


def test_gcs_and_bigquery_contract(tmp_path):
    create(tmp_path / "input", 2)
    prepare(tmp_path / "input/manifest.json", tmp_path / "run", True)
    gcs, bq = Mock(), Mock()
    job = bq.load_table_from_uri.return_value
    job.output_rows, job.errors, job.job_id = 8, None, "observed-id"
    report = upload_batch(tmp_path / "run", "demo-project", "demo-bucket", "raw_test",
                          storage_client=gcs, bigquery_client=bq)
    gcs.bucket.return_value.blob.return_value.upload_from_filename.assert_called_once()
    assert gcs.bucket.return_value.blob.return_value.upload_from_filename.call_args.kwargs[
        "if_generation_match"] == 0
    args = bq.load_table_from_uri.call_args
    assert args.args[0].startswith("gs://demo-bucket/purchase-batches/")
    assert args.args[1] == "demo-project.raw_test.raw_lines"
    assert args.kwargs["job_config"].write_disposition == "WRITE_APPEND"
    assert report["output_rows"] == 8
    assert json.loads((tmp_path / "run/cloud.json").read_text())["job_id"] == "observed-id"


def test_tamper_stops_before_network(tmp_path):
    create(tmp_path / "input", 1)
    prepare(tmp_path / "input/manifest.json", tmp_path / "run", True)
    with (tmp_path / "run/raw.ndjson").open("a") as handle:
        handle.write("{}\n")
    gcs, bq = Mock(), Mock()
    with pytest.raises(ValueError, match="integrity"):
        upload_batch(tmp_path / "run", "demo-project", "demo-bucket", "raw_test",
                     storage_client=gcs, bigquery_client=bq)
    assert not gcs.mock_calls and not bq.mock_calls


def test_existing_object_and_regional_job_replay(tmp_path):
    from google.api_core.exceptions import Conflict, PreconditionFailed

    create(tmp_path / "input", 2)
    prepare(tmp_path / "input/manifest.json", tmp_path / "run", True)
    gcs, bq = Mock(), Mock()
    blob = gcs.bucket.return_value.blob.return_value
    blob.upload_from_filename.side_effect = PreconditionFailed("exists")
    blob.download_as_bytes.return_value = (tmp_path / "run/raw.ndjson").read_bytes()
    bq.load_table_from_uri.side_effect = Conflict("exists")
    job = bq.get_job.return_value
    job.output_rows, job.errors, job.job_id = 8, None, "existing-job"
    result = upload_batch(tmp_path / "run", "demo-project", "demo-bucket", "raw_test",
                          location="us-central1", storage_client=gcs, bigquery_client=bq)
    assert result["location"] == "us-central1"
    assert bq.load_table_from_uri.call_args.kwargs["location"] == "us-central1"
    bq.get_job.assert_called_once_with(
        bq.load_table_from_uri.call_args.kwargs["job_id"], location="us-central1")
    blob.download_as_bytes.return_value = b"wrong object"
    with pytest.raises(ValueError, match="does not match"):
        upload_batch(tmp_path / "run", "demo-project", "demo-bucket", "raw_test",
                     location="us-central1", storage_client=gcs, bigquery_client=bq)
