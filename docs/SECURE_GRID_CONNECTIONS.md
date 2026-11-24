# Secure grid connections — GridPass Guard

Status: proposal, not implemented or certified. Updated 2026-11-24.

## Decision

Build a small, open-source, application-aware enforcement layer for flexible electricity connections. Reuse the existing GridPass Flexibility evaluator for resource sizing and operational feasibility; do not turn that offline Python model into a real-time controller or duplicate its optimizer. The edge component should have its own testable interface and release cycle. Evaluate the existing GridPass controller implementation before adding any new runtime. Prefer Rust for a new minimal enforcement core; use mature dependencies rather than writing cryptography or protocol stacks.

## Problem and scope

A flexible connection agreement can impose time-dependent import/export limits, response deadlines, permitted resources, recovery rules and fallback requirements. An EMS or aggregator optimizes operations; it must not have authority to override the connection agreement. GridPass Guard independently checks permitted requests, monitors the point of connection and applies an approved local fallback when necessary. It is not a generic firewall, grid protection relay, autonomous dispatch optimizer or replacement for certified protection equipment.

Target first deployment: one commercial or industrial site with a meter and battery or controllable load. Phase 1 runs only with synthetic devices in an isolated test environment.

## Architecture and trust boundary

- **Size:** the existing offline model produces feasible schedules, resource envelopes and explicit assumptions. Model output does not authorize live control.
- **Control:** authorized operator constraints enter through a narrow protocol adapter. An independently configured, bounded local policy governs all EMS requests. A meter provides actual signed/directional net active power, validity and freshness. A local controller selects an allowed request and sends it only to explicitly authorized devices. No internet dependency for enforcement.
- **Prove:** export a versioned, reproducible trace of policy changes, meter health, requested/allowed/applied values, acknowledgements, transitions and observed limit excursions. Include model/config/software versions and clock quality. Use signed checkpoints and independently retained copies to make omissions or modifications detectable. Do not confuse signed logs with proof of physical power or guaranteed compliance.

Separate grid-operator authorization from EMS authorization. Authenticate peers, use least privilege, reject stale/duplicate/out-of-order or invalid inputs, bound command authority, rate and freshness, and record configuration provenance. Transport authentication is not sufficient authorization. Local device networks with legacy Modbus must be isolated and accessible only through a controlled interface. Enforce safe defaults for restart and loss of authority; use established TLS and key management libraries. Keys and customer data never enter the repository.

The effective limit is the intersection of the signed/authorized connection policy, valid dynamic limits and the site's equipment constraints. Use explicit units, sign conventions, measurement intervals, tolerances, ramp rates, validity windows and monotonic timing. Do not infer fallback power from a generic number: use the operator-approved site-specific fallback profile. If the system lacks current measurement, controllable capacity or actuator acknowledgement, signal an unsafe/unverified state and invoke the approved fail-safe path; never report successful enforcement just because a command was clipped.

A controller can constrain actual power only if metering, controllable reserve, latency, actuator authority and protection arrangements are sufficient. An independent field assessment must establish this. No claim of zero excursions, safety certification, CRA/NIS2 compliance or DSO acceptance is made by a simulation.

## Reuse candidates (validate versions, interoperability and licenses)

| Candidate | Purpose | Gate |
|---|---|---|
| [OpenLEADR Rust](https://github.com/OpenLEADR/openleadr-rs) | OpenADR VEN/VTN integration for operator signals | Pin version; verify 3.1 compatibility with operator requirements and production identity provider. No assumption every DSO supports OpenADR. |
| [GEISA specification](https://github.com/geisa/specification), [conformance](https://github.com/geisa/conformance) | Grid-edge platform interoperability and security | Map requirements and published test cases; no conformance claim until applicable tests pass. Specification and code have different licensing. |
| [OpenEMS](https://github.com/OpenEMS/openems) | Reference/device integration and interoperability tests | Review license and avoid embedding a second EMS. |
| [tokio-modbus](https://github.com/slowtec/tokio-modbus) | Local device adapter | Validate register map, byte order, timing and device access constraints; not a security protocol. |
| [rustls](https://github.com/rustls/rustls) | Established TLS implementation | Pin reviewed versions; test certificate lifecycle and peer authorization separately. |
| [NIST SP 1800-32](https://csrc.nist.gov/pubs/sp/1800/32/final) | DER security reference architecture | Map authenticated communication, integrity, monitoring and independent evidence to test cases. |

Evaluate SunSpec device models, IEEE 2030.5 and other local protocols when an actual operator/site requires them. Do not introduce a protocol or framework without a customer requirement and passing integration tests.

## First release: offline reference implementation

One demonstrator using synthetic meter, battery and flexible load. Expose a typed, versioned contract policy and deterministic request/measurement interfaces. Provide a command-line replay of a fixture, an evidence export and tests with documented expected outcomes. No connection to real plant equipment. Keep simulator-only tooling separate from the runtime.

| Gate | Expected observable result |
|---|---|
| G1 Contract policy | Import/export sign, units, validity, limits, bounds and fallback checked; reject ambiguous or invalid policy. |
| G2 Authorization | Unauthorized or stale requests do not change effective policy; legitimate requests are accepted only within authority. |
| G3 Limit enforcement | Under stated simulated metering/actuation assumptions, accepted requests remain inside configured limits; actual observed power is evaluated separately. |
| G4 Degraded operation | Missing communications, invalid/stale meter data, unavailable resources or rejected actuator commands produce the approved fallback request or an explicit unverified/unsafe state, never a false pass. |
| G5 Restart and evidence | Restore valid configuration safely; log decisions, faults, acknowledgements and excursions. Verify trace integrity and reproduce results from fixture and versioned config. |
| G6 Repeatable release | CI executes normal and fault cases; dependency audit, licensing and documented limitations; independent reviewer can reproduce from a clean checkout. |

First milestone is a simulator demonstration, not deployment authorization. Actual hardware pilot requires operator approval, commissioning plan, site-specific test criteria, fail-safe hardware where needed, and professional protection design.

## Market and funding

Open-source core, policy schema, adapters and conformance fixtures: proposed Apache-2.0 for original GridPass code, subject to dependency and contributor review. Revenue: paid site assessment, integration, deployment, validated evidence and maintenance. No proprietary EMS, no new hardware inventory, no certification claims. Use public or synthetic datasets for demos.

Priority commercial test: interview a DSO and an aggregator/EMS vendor. Ask how connection limits are issued, verified, enforced, updated and handled during loss of communication. Ask whether independent local control and evidence solve a real acceptance obstacle. Seek a written pilot scope with actual acceptance criteria and a paid integration budget.

Public opportunities, checked 2026-11-24:
- [GEISA 1.0 draft review](https://lf-energy.atlassian.net/wiki/spaces/GEISA/pages/404422657/Specification%2BDraft): comments due **2026-12-11**. Review applicable security and platform requirements; contribute specific feedback based on the demonstrator. Participate via [LF Energy GEISA](https://lfenergy.org/projects/geisa/).
- [NLnet Restack](https://nlnet.nl/restack/): deadline **2027-01-03 12:00 CET**. Check eligibility and fit for reusable secure interoperability/evidence infrastructure, not a vertical commercial controller alone. The [FAQ](https://nlnet.nl/restack/faq/) says applicants should write their own proposal and disclose and explain any use of generative AI. No application generated or submitted here.
- [CIPHER Open Call #1](https://cipher-eu.com/open-call-1/): deadline **2027-01-06 17:00 CET**, up to EUR 60,000, 50% eligible-cost co-funding. Evaluate R1 energy-sector cyber-range integration using a simulated GridPass site and LabWired where technically appropriate; check ownership/IP terms, entity eligibility, costs, end-user participation and cash flow before committing.
- [Digital Europe cybersecurity call](https://cybersecurity-centre.europa.eu/funding-opportunities/calls-proposals/strengthening-european-cybersecurity-technologies-capacities-and-preparedness-digital-eccc-2027_en): deadline **2027-01-14 17:00 CET**. Participate as a bounded technical contributor if a suitable eligible consortium and realistic cost coverage are confirmed.

## Action sequence (proposed, not commitments)

1. Inventory existing controller code and site adapters. Freeze a minimal policy/measurement interface, fixture and test acceptance gates. Keep current evaluator backlog intact.
2. Build the simulator-only vertical slice and publish a reproducible example. Target one week of focused engineering after inventory, not an estimated delivery commitment.
3. Review GEISA and request community feedback before 11 December. Seek one grid operator and one aggregator/EMS partner for requirements review; do not publish confidential network/site information.
4. Decide grant go/no-go before the January deadlines. Prioritize no-cost technical validation and partner demand; no speculative 50% co-financing without cash coverage.

Success means an independent reviewer can run the demo, see which requests were authorized or rejected, identify measured limit excursions and distinguish genuine physical enforcement from an unverified simulation. Commercial validation requires a prospective operator to supply acceptance requirements and agree to a scoped pilot.
