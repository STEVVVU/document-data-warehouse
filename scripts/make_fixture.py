import argparse
import csv
import json
from pathlib import Path


def create(root: Path, rows_per_source=100, *, documents=True):
    root.mkdir(parents=True, exist_ok=True)
    sources = []
    expected = []
    for source in range(4):
        rows = []
        for i in range(rows_per_source):
            invoice = i // 10
            rows.append({
                "line_id": f"line-{i}", "invoice_id": f"invoice-{invoice}",
                "supplier_id": f"supplier-{invoice % 20}",
                "supplier_name": f"Supplier {invoice % 20}",
                "invoice_date": f"2026-01-{invoice % 28 + 1:02d}",
                "sku": f"sku-{i % 50}", "description": f"Component {i % 50}",
                "category": ["Hardware", "Office", "Packaging"][i % 3],
                "country": ["US", "DE", "GB", "CA"][source],
                "currency": "EUR" if invoice % 3 == 0 else "USD",
                "quantity": i % 5 + 1, "unit_price_cents": 100 + i % 1000,
                "revision": 1, "deleted": False,
            })
        expected.extend(rows)
        if source == 0:
            name = "supplier-a.csv"
            with (root / name).open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0])
                writer.writeheader()
                writer.writerows(rows)
            sources.append({"name": "supplier-a", "path": name, "kind": "csv"})
        elif source == 3 and documents:
            (root / "invoice.txt").write_text(
                "Synthetic purchase invoice capture for offline contract testing.\n" +
                "\n".join(f"{r['invoice_id']} {r['line_id']} {r['description']} "
                          f"quantity={r['quantity']} cents={r['unit_price_cents']}"
                          for r in rows), encoding="utf-8")
            (root / "captured-extraction.json").write_text(
                json.dumps({"lines": rows}, indent=2), encoding="utf-8")
            sources.append({"name": "document-d", "path": "invoice.txt", "kind": "document",
                            "mime_type": "text/plain",
                            "fixture_response": "captured-extraction.json"})
        else:
            name = f"supplier-{source}.json"
            (root / name).write_text(json.dumps(rows, indent=2), encoding="utf-8")
            sources.append({"name": f"supplier-{source}", "path": name, "kind": "json"})
    (root / "manifest.json").write_text(json.dumps({"sources": sources}, indent=2),
                                        encoding="utf-8")
    return expected


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--rows-per-source", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.rows_per_source <= 50000:
        parser.error("rows per source must be 1..50000")
    create(args.output, args.rows_per_source)
