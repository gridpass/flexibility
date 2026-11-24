"""Private child process for one evaluation. Not a network entry point."""
import json
import sys

def main():
    import resource
    # Bound native solver memory, output and CPU as well as the parent wall clock.
    memory = 1536 * 1024 * 1024
    output = 16 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_FSIZE, (output, output))
    resource.setrlimit(resource.RLIMIT_CPU, (45, 46))
    from .budget import check_budget
    from .interface import evaluate_request
    try:
        request = json.load(sys.stdin)
        operation, payload = request["operation"], request["payload"]
        check_budget(operation, payload)
        value = evaluate_request(operation, payload)
        json.dump({"result":value}, sys.stdout, allow_nan=False, separators=(",",":"))
    except (ValueError, KeyError, TypeError, OverflowError):
        # Never include submitted data or arbitrary exceptions in a network error.
        json.dump({"error":"invalid_evaluation"}, sys.stdout)
    except Exception:
        json.dump({"error":"evaluation_failed"}, sys.stdout)

if __name__ == "__main__":
    main()
