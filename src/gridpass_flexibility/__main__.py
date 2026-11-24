import argparse
import json
from pathlib import Path
from . import assess, SCHEMA

def main():
    p = argparse.ArgumentParser(description="Independent site flexibility assessment")
    p.add_argument("scenario", nargs="?", type=Path)
    p.add_argument("--schema", action="store_true")
    args = p.parse_args()
    if args.schema:
        print(json.dumps(SCHEMA, indent=2))
        return 0
    if args.scenario is None:
        p.error("provide a scenario JSON file or --schema")
    try:
        result = assess(json.loads(args.scenario.read_text()))
    except (OSError, ValueError) as exc:
        p.error(str(exc))
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["valid"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
