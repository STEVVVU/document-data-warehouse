import argparse
import json
import sys
from pathlib import Path

from warehouse.build import build, doctor
from warehouse.ingest import prepare


def main():
    parser = argparse.ArgumentParser(description="Purchase document warehouse")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--manifest", type=Path, required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    prepare_parser.add_argument("--fixture-extraction", action="store_true")
    prepare_parser.add_argument("--model")
    prepare_parser.add_argument("--project")
    prepare_parser.add_argument("--location", default="us-central1")
    for name in ("build", "doctor", "upload"):
        sub = commands.add_parser(name)
        sub.add_argument("--run-dir", type=Path, required=True)
        if name != "upload":
            sub.add_argument("--database", type=Path)
        if name == "build":
            sub.add_argument("--full-refresh", action="store_true")
        if name in ("build", "upload"):
            sub.add_argument("--cloud", action="store_true")
            sub.add_argument("--project")
            sub.add_argument("--dataset")
            sub.add_argument("--location", default="US")
        if name == "upload":
            sub.add_argument("--bucket", required=True)
    args = vars(parser.parse_args())
    command = args.pop("command")
    try:
        if command == "prepare":
            args["manifest_path"] = args.pop("manifest")
            result = prepare(**args)
        elif command == "build":
            result = build(**args)
        elif command == "doctor":
            result = doctor(**args)
        else:
            if not args.pop("cloud") or not args["project"] or not args["dataset"]:
                raise ValueError("upload requires --cloud, --project and --dataset")
            from warehouse.cloud import upload_batch
            result = upload_batch(**args)
        print(json.dumps(result, sort_keys=True))
    except (ValueError, RuntimeError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
