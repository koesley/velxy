# VELXTRIA V57.2 — Living Business Graph

Adds `sovereign_business_graph_v57.py` to the existing V57.1 project.

## Features
- Workspace-isolated, manually curated entities: customer, product, service, supplier, team, process, metric, risk, channel, system.
- Directed relationships and explanations, evidence source, confidence labels, archival (with dependent edges).
- Descriptive blind spot checks: unconnected entities, hypotheses, shared dependencies.
- Owner/editor writes; viewer read-only; audit events, CSRF-protected portal actions.
- Responsive dark-purple interface and JSON API.
- No paid APIs, no arbitrary SQL, no autonomous actions.

## Launch
Set `VELXTRIA_LOCAL_STUDIO=1`, `VELXTRIA_DEPLOYMENT_MODE=local`; run `python portal.py`; open `/sovereign-business-graph-v57`.

## Limits
Data is user-entered and not automatically verified. No physics-based graph canvas, inferred causality, autonomous discovery, or production certification. Views capped at 250 nodes and 500 edges. Existing databases are extended using CREATE TABLE IF NOT EXISTS. Back up databases before upgrading.
