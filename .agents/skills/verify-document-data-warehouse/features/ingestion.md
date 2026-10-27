# Ingestion

## Sub-features

CSV, JSON and document inputs; explicit fixture extraction; Gemini structured extraction; reject receipts; duplicate keys and provenance.

## How to get to it (user POV)

Run `python -m warehouse prepare --manifest fixtures/manifest.json --output .runs/demo --fixture-extraction`.

## Driving it with CLI

Run scripts/verify.py. Inspect raw.ndjson and prepare.json. Replay identical input and compare stable record identifiers and source hashes. Invalid rows must appear in rejects.ndjson and the command must fail by default before warehouse loading.

## Gotchas

Fixture responses prove transport-independent parsing and integrity, not Gemini accuracy. Four synthetic source systems do not prove four independently published data sources.
