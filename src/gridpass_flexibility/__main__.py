import argparse
import json
from pathlib import Path
from . import SCHEMA
from .interface import evaluate_request

def main():
    p = argparse.ArgumentParser(description="Independent site flexibility assessment")
    p.add_argument("scenario", nargs="?", type=Path)
    p.add_argument("--schema", action="store_true")
    mode=p.add_mutually_exclusive_group()
    mode.add_argument("--dispatch", action="store_const", const="dispatch", dest="operation", help="Chronological optimization")
    mode.add_argument("--compare-designs", action="store_const", const="compare_designs", dest="operation", help="Compare explicit equipment designs")
    mode.add_argument("--profile", action="store_const", const="profile", dest="operation", help="Evaluate supplied commitment profile and cases")
    mode.add_argument("--size", action="store_const", const="size", dest="operation", help="Optimize shared capacity across cases")
    mode.add_argument("--stress", action="store_const", const="stress", dest="operation", help="Generate annual commitment stress cases")
    p.set_defaults(operation="screen")
    args = p.parse_args()
    if args.schema:
        print(json.dumps(SCHEMA, indent=2))
        return 0
    if args.scenario is None:
        p.error("provide a scenario JSON file or --schema")
    try:
        data=json.loads(args.scenario.read_text())
        result=evaluate_request(args.operation,data)
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        p.error(str(exc))
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result.get("valid",result.get("status") not in ("solver_failed","replay_failed","infeasible")) else 2

if __name__ == "__main__":
    raise SystemExit(main())
