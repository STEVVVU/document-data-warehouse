import hashlib
import json
import re
from pathlib import Path

from google.cloud import bigquery, storage

from warehouse.domain import canonical, sha


def validate_identifiers(project, dataset):
    if not isinstance(project, str) or not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project):
        raise ValueError("invalid project identifier")
    if not isinstance(dataset, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,100}", dataset):
        raise ValueError("invalid dataset identifier")


def upload_batch(run_dir: Path, project: str, bucket: str, dataset: str, *, location="US",
                 storage_client=None, bigquery_client=None):
    validate_identifiers(project, dataset)
    if not isinstance(location, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,60}", location):
        raise ValueError("invalid BigQuery location")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]", bucket):
        raise ValueError("invalid bucket identifier")
    path = run_dir / "raw.ndjson"
    prepared = json.loads((run_dir / "prepare.json").read_text(encoding="utf-8"))
    digest = sha(path)
    if digest != prepared["raw_sha256"] or prepared["rejects"]:
        raise ValueError("prepared batch integrity check failed")
    storage_client = storage_client or storage.Client(project=project)
    bigquery_client = bigquery_client or bigquery.Client(project=project)
    object_name = f"purchase-batches/{digest}.ndjson"
    blob = storage_client.bucket(bucket).blob(object_name)
    # Content-addressed names and a create-only generation precondition protect retries.
    from google.api_core.exceptions import PreconditionFailed
    try:
        blob.upload_from_filename(str(path), content_type="application/x-ndjson",
                                  if_generation_match=0)
    except PreconditionFailed:
        if hashlib.sha256(blob.download_as_bytes()).hexdigest() != digest:
            raise ValueError("existing object does not match the prepared batch") from None
    uri = f"gs://{bucket}/{object_name}"
    schema = []
    with path.open(encoding="utf-8") as handle:
        sample = json.loads(handle.readline())
    for name, value in sample.items():
        kind = "BOOLEAN" if isinstance(value, bool) else (
            "INTEGER" if isinstance(value, int) else "STRING")
        if name == "invoice_date":
            kind = "DATE"
        elif name == "_load_time":
            kind = "TIMESTAMP"
        schema.append(bigquery.SchemaField(name, kind, mode="REQUIRED"))
    destination = f"{project}.{dataset}.raw_lines"
    config = bigquery.LoadJobConfig(
        schema=schema, source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )
    job_id = "purchase_" + hashlib.sha256((destination + location + digest).encode()).hexdigest()
    from google.api_core.exceptions import Conflict
    try:
        job = bigquery_client.load_table_from_uri(
            uri, destination, job_config=config, job_id=job_id, location=location)
    except Conflict:
        job = bigquery_client.get_job(job_id, location=location)
    job.result(timeout=300)
    if job.errors:
        raise RuntimeError("BigQuery load job failed")
    report = {"object_uri": uri, "raw_sha256": digest, "job_id": job.job_id,
              "output_rows": job.output_rows, "destination": destination,
              "location": location, "mode": "live-gcp"}
    if job.output_rows != prepared["rows"]:
        raise RuntimeError("BigQuery loaded an unexpected number of rows")
    (run_dir / "cloud.json").write_text(canonical(report), encoding="utf-8")
    return report
