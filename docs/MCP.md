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

Payloads are JSON objects, not filenames or URLs. The MCP server and CLI call the same Python evaluation functions. Results are structured JSON and conventional MCP text content. The server provides local stdio or loopback-only Streamable HTTP transport. An agent-request complexity guard limits resource-interval count and mixed-integer complexity (12,000 binary variables per dispatch); it is not a production workload isolation mechanism. Causal replay is additionally limited to 96 executed steps, 96 lookahead steps and a 60-second replay-wide solver budget.

The hosted GridPass public MCP remains a separate integration target. For a public solver endpoint, use authenticated or rate-limited isolated workers, request size and time limits, bounded queues, and prevent disclosure of uploaded site information. Do not expose the local server directly to the Internet. It cannot control equipment or submit customer leads.
