import argparse
import json
from pathlib import Path
from . import assess, SCHEMA

def main():
    p = argparse.ArgumentParser(description="Independent site flexibility assessment")
    p.add_argument("scenario", nargs="?", type=Path)
    p.add_argument("--schema", action="store_true")
    p.add_argument("--dispatch", action="store_true", help="Chronological optimization (install optimization extra)")
    p.add_argument("--compare-designs", action="store_true", help="Compare designs from JSON {scenario, designs}")
    p.add_argument("--profile", action="store_true", help="Evaluate supplied profile and scenarios")
    args = p.parse_args()
    if args.schema:
        print(json.dumps(SCHEMA, indent=2))
        return 0
    if args.scenario is None:
        p.error("provide a scenario JSON file or --schema")
    try:
        data=json.loads(args.scenario.read_text())
        if args.dispatch:
            from .dispatch import evaluate
            result=evaluate(data)
        elif args.compare_designs:
            from .dispatch import compare_designs
            result=compare_designs(data["scenario"],data["designs"])
        elif args.profile:
            from .profiles import evaluate_profile
            result=evaluate_profile(data["profile"],data["scenarios"])
        else:
            result=assess(data)
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        p.error(str(exc))
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result.get("valid",result.get("status")!="solver_failed") else 2

if __name__ == "__main__":
    raise SystemExit(main())
