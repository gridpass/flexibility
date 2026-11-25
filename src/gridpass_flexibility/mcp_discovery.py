"""Discoverable guidance and existing synthetic examples for MCP clients."""
from importlib.resources import files
import json
from pathlib import Path


EXAMPLES = {
    "screen": "data-centre.json", "dispatch": "chronological.json",
    "compare_designs": "design-comparison.json", "profile": "profile-check.json",
    "size": "capacity-sizing.json", "stress": "annual-stress.json",
    "causal": "causal-replay.json", "economics": "lifecycle-economics.json",
}

GUIDE = """# Assess a site against an offered grid import limit

Use evaluate_flexibility with an operation and its JSON payload. The same open
engine powers the CLI; this interface adds no solver or live equipment control.

## Choose the calculation
- screen: simple repeated-event screening with declared resources.
- dispatch: chronological feasibility and resource schedule.
- compare_designs: compare the supplied equipment additions.
- profile: check supplied scenarios against a declared commitment profile.
- size: size shared battery/generator capacity across supplied scenarios.
- stress: test generated restrictions and specified resource outages.
- causal: replay decisions using observed data and announced events.
- economics: compare supplied alternatives and lifecycle cost assumptions.

## Get the existing contracts
Read gridpass://evaluation/schema/request and gridpass://evaluation/schema/response.
Read gridpass://evaluation/examples/{operation} for a complete {operation, payload}
request. Every example is synthetic, not site evidence or a default to fill gaps.
Schema checks are opt-in; physical validation and request budgets still apply.

## Prepare evidence
Separate measured data, user-supplied assumptions and indicative public data.
Record source, date, time step and units in the assessment. Obtain the offered
import limit and its timing, notice and recovery conditions from the user or
their supplied agreement. Public hosting-capacity figures are not a site limit.
Do not invent missing inputs or replace a missing value with zero.
Use MW for power, MWh for energy, hours for duration, minutes for notice and EUR
for costs as specified by each schema. kW/1000 = MW; kWh/1000 = MWh. MVA cannot
be converted to MW without power factor and the relevant operating conditions.

## Interpret results
Report feasibility, uncovered power/energy, resource sizes and costs only where
the selected operation returns them. Preserve evidence hashes when available.
Distinguish invalid input, solver failure, incomplete analysis and infeasibility.
State assumptions and scope; modeled feasibility is not grid approval, equipment
certification or measured performance. No outreach or physical control occurs.
Agent budgets include 500,000 resource-interval units per aggregate request and
12,000 binary variables per dispatch. Causal replay allows 96 steps and 96 lookahead intervals. Sizing,
causal and economics solver budgets are at most 60 seconds; other case limits
also apply. Reduce or split a case only if its engineering meaning is preserved.
"""

WORKFLOW = """Assess whether the user's site can operate within an offered grid import limit.
1. Read gridpass://evaluation/guide and gridpass://evaluation/schema/request.
2. Identify the decision, site demand, offered import limit, restriction timing
   and available flexibility. Ask for missing required inputs. Label measured
   data, user assumptions and indicative public data separately. Do not use
   public hosting capacity as the offered limit or invent site values. Check
   units; MVA requires power factor and operating conditions before using MW.
3. Choose the smallest suitable existing operation. Read its synthetic request
   at gridpass://evaluation/examples/{operation}; replace it only with supplied
   inputs or explicit user assumptions. Never present the example as site data.
4. Call evaluate_flexibility. Use further existing operations only when they
   answer the decision, such as comparing additions or sizing a battery.
5. Report the decision, returned quantities, assumptions, evidence and remaining
   gaps. Distinguish modeled feasibility from approval and measured performance.
   Treat incomplete or failed evaluations explicitly. Do not control equipment,
   send messages, submit enquiries or imply operator acceptance.
"""


def example_request(operation: str) -> dict:
    """Read an allowlisted example from the single repository/package data set."""
    if operation not in EXAMPLES:
        raise ValueError("Unknown evaluation example operation")
    try:
        directory = files("gridpass_flexibility.examples")
    except ModuleNotFoundError:
        # Source/editable checkouts may not expose the data-only package mapping.
        directory = Path(__file__).resolve().parents[2] / "examples"
    payload = json.loads(directory.joinpath(EXAMPLES[operation]).read_text(encoding="utf-8"))
    return {"operation": operation, "payload": payload}
