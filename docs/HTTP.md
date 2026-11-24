# Bounded evaluation service

The optional Linux service exposes the canonical evaluation interface to an authenticated upstream, not directly to anonymous Internet clients. Install the host extra:

    pip install ".[host]"
    # Inject GRIDPASS_EVALUATION_TOKEN through a private service credential.
    gridpass-flexibility-http --port 8766

The service binds only to loopback. Use a TLS proxy and a high-entropy token (at least 32 ASCII characters) distinct from all other GridPass credentials. Keep proxy access logs free of request bodies and authorization headers. Do not expose the service without a separate authorization and abuse-control layer.

GET /health returns only status and engine version. POST /evaluate requires Authorization: Bearer <token>, Content-Type: application/json, and a JSON object containing operation and payload. For example, the dispatch operation uses the contents of examples/chronological.json as its payload. All eight operations use the existing evaluate_request function; the same numerical complexity checks apply as in the local MCP server. A solved or modeled-infeasible result returns HTTP 200 and a result object. Invalid envelope, unauthorized, oversized, busy, invalid input, process failure, and timeout return 400, 401, 413, 429, 422, 503, and 504 respectively. The response does not echo exception messages. All responses are marked no-store.

One request at a time by default, optionally two; no wait queue. Requests have a 1 MiB limit and a five-second streaming-body deadline. A fresh subprocess evaluates each accepted request with a minimal environment, single-thread BLAS settings, 1.5 GiB virtual-address limit, 16 MiB output limit, CPU limit and 45-second wall timeout. The parent reaps timed-out subprocesses. Anonymous temporary files hold input/output only for the request lifetime. These are resource and accidental-disclosure safeguards, not a sandbox for untrusted executable code. The service accepts JSON data, never code. Run under a dedicated unprivileged account with a service-level memory/CPU limit, restricted filesystem and no unrelated credentials or access to customer records.

Tests exercise real subprocess parity with the canonical screen, dispatch and sizing operations, authorization, malformed/nonfinite input, complexity and byte limits, concurrent rejection, timeout and recovery. The service does not control real assets or accept enquiries. Local tests do not establish production exposure, security audit, availability or field validation.

Integration gate: route the existing GridPass public API/MCP through an explicitly configured TLS upstream with separately provisioned credentials; verify numeric parity, safe error mapping, access controls, and actual live deployment. Do not silently fall back to a second numerical implementation for advanced evaluation.


## Hosted smoke test

The initial GridPass public deployment was verified on 2026-11-24 with v0.3.7. From an installed checkout with the matching solver dependencies, run:

    python scripts/verify_hosted.py

The script submits only the repository's synthetic examples to the public browser API and MCP endpoint, compares all eight results with the local canonical evaluator, and checks invalid input and explicit-consent rejection. It is intentionally not part of automatic CI. It does not submit an enquiry, expose the upstream credential, perform a stress load test, or assert availability guarantees.
