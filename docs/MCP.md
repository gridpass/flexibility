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

## Connection assessment workflow

The primary job is: **Can this site operate within an offered grid import limit,
and which equipment options satisfy the supplied conditions?**

The MCP still has one numerical tool. Standard MCP resources expose the existing
contracts and synthetic examples, so an agent can prepare a valid request without
guessing the payload or requiring a separate repository checkout.

| MCP resource | Content |
|---|---|
| `gridpass://evaluation/guide` | Operation selection, units, required input evidence and scope |
| `gridpass://evaluation/schema/request` | Existing versioned request JSON Schema |
| `gridpass://evaluation/schema/response` | Existing versioned response JSON Schema |
| `gridpass://evaluation/examples/{operation}` | Synthetic request envelope for one of the eight operations |

The optional `assess_connection` MCP prompt guides the same workflow. Clients that
support prompts can offer it as a user-selected starting point. The prompt does
not run calculations; the client calls `evaluate_flexibility` after it has the
necessary inputs. Resource and prompt visibility depends on the MCP client.

Start by recording the load time series, offered limit and restriction windows,
available equipment, timing and cost assumptions. Label every input as measured,
operator-provided, user-supplied assumption or synthetic. Use `dispatch` to check a
supplied configuration, `compare_designs` for alternative equipment packages,
and `size` when capacity must be selected. Use `economics` only with the required
financial assumptions and coverage. Report the returned shortfalls, feasibility,
cost basis and evidence with remaining input gaps.

Public DSO datasets can supply separate screening context through an existing
data connector. They must not silently supply the operational cap. Preserve
import/export direction, source date and units; demand headroom in MVA cannot be
treated as MW without a stated power factor. The numerical server does not infer
the serving operator or retrieve current network capacity.

### Reproduce a complete MCP assessment

After installing the agent extra, run:

```sh
python scripts/demo_connection_assessment.py > connection-assessment.json
```

The script starts the installed MCP over stdio, discovers resources and the
assessment prompt, reads the canonical schemas and the existing `compare_designs`
example through MCP, validates the request, calls the numerical tool, and validates
the response. It writes the full request, result and evidence as JSON.

The synthetic example has a 20 MW load, a normal import cap of 23 MW, and a 15 MW
cap during two restrictions lasting four and two hours in a twelve-hour horizon.
It compares no flexibility, a 3 MW / 12 MWh battery, and the same battery with
3 MW of generation and 2 MW of shiftable load. The battery includes a 1 MWh
reserve and 95% charge/discharge efficiencies. Resource energy budgets and
recovery constraints come from the example. Its costs are illustrative inputs,
not equipment quotations or annual savings.

This addition changes discovery and guidance only. It reuses the existing SDK,
schemas, examples and evaluator. It does not change the numerical engine, the
tool's request/response format, or its input-validation behaviour. The hosted
gateway has a separate deployment and must be checked independently.

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
