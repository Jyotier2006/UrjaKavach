# Requirement traceability

| ID | Product surface | Implementation | Evidence status |
|---|---|---|---|
| R1 | Fleet, asset signals, solar, IR inspection | Artifact telemetry, feature map, upload endpoint | Synthetic demo; real ingestion requires datasets |
| R2 | Replay, evidence, compare, performance | B0 and normal-behavior demo; model adapters | Synthetic validation only; CARE metrics unavailable |
| R3 | Health states, attention list, alerts | Criticality, acknowledgement, replay | Browser/API tests |
| R4 | Maintenance planner | Python CP-SAT, skills/windows/parts/shifts, offline plan catalog | Solver artifacts and constraint tests |
| R5 | Cost of waiting, assumptions | Python Monte Carlo loss domain | Numeric tests; assumptions explicitly illustrative |
| R6 | Operator, technician, manager | Responsive Next.js screens and local demo role switch | Browser checks; roles are not production auth |
| R7 | Alert center, replay, integration | Python MQTT simulator/consumer, WebSockets, Slack optional | Local tests; external delivery requires webhook and running broker |

The app About page repeats this mapping and distinguishes implemented workflows from missing empirical evidence.
