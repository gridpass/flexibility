# Agent integration

Install the package with the agent extra from this repository:

```sh
pip install ".[agent]"
```

A compatible local MCP client can launch the installed command:

```json
{
  "mcpServers": {
    "gridpass-flexibility": {
      "command": "gridpass-flexibility-mcp"
    }
  }
}
```

Use the single generic `evaluate_flexibility` tool:

| Operation | Payload example |
|---|---|
| screen | examples/data-centre.json |
| dispatch | examples/chronological.json |
| compare_designs | examples/design-comparison.json |
| profile | examples/profile-check.json |
| size | examples/capacity-sizing.json |
| stress | examples/annual-stress.json |
| causal | examples/causal-replay.json |
| economics | examples/lifecycle-economics.json |

Payloads are JSON objects, not filenames or URLs. The MCP server and CLI call the same Python evaluation functions. Results are structured JSON and conventional MCP text content. The server provides local stdio or loopback-only Streamable HTTP transport. An agent-request complexity guard limits resource-interval count and mixed-integer complexity (12,000 binary variables per dispatch); it is not a production workload isolation mechanism. Causal replay is additionally limited to 96 executed steps, 96 lookahead steps and a 60-second replay-wide solver budget.

The [bounded HTTP service](HTTP.md) provides an authenticated canonical upstream; routing the existing hosted GridPass public MCP to it remains a separate integration target. For a public solver endpoint, use authenticated or rate-limited isolated workers, request size and time limits, bounded queues, and prevent disclosure of uploaded site information. Do not expose the local server directly to the Internet. It cannot control equipment or submit customer leads.

## Versioned evaluation contract

Export the packaged Draft 2020-12 JSON Schemas without starting a server:

```sh
gridpass-flexibility --evaluation-schema request > request-v1.json
gridpass-flexibility --evaluation-schema response > response-v1.json
```

The request is the existing `{"operation": "dispatch", "payload": {...}}`
object. The response schema validates an operation-tagged view
`{"operation": "dispatch", "result": {...}}` of the existing unwrapped
result; this is a validation wrapper, not a change to the HTTP or MCP wire
format. Both schemas have stable versioned `$id` values. Request definitions
cover all eight operations, nested equipment types, events, capacity options,
tariffs, fuel and investment assumptions. Unknown request properties are
rejected by the strict schema. Response definitions require the stable core
fields, outcome variants, schedule columns and applicable evidence hashes;
additional diagnostic fields can evolve without a schema-version change.

Python clients with the optimization, agent or host extra can use
`gridpass_flexibility.interface_schema.validate_evaluation(direction, operation, value)`
to validate a payload or result. This is an opt-in conformance check; existing
service input handling is unchanged. The engine still validates cross-field
conditions such as equal series lengths, overlapping events, resource limits,
physical feasibility and annual coverage. Hosted complexity and isolation
limits are separate. The schemas do not certify any equipment or commitment.
The live parity script validates both the request and each browser, MCP and
local result before comparing JSON values.
