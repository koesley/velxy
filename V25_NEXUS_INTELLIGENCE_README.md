# VELXTRIA V25 — Nexus Intelligence

Local SQLite milestone built on V24 Oracle. Back up your existing database and keep `VELXTRIA_DATA_DIR` unchanged before replacing code.

## Start

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```

Open `http://127.0.0.1:8878/nexus-intelligence` and select an Empire workspace.

## Features

- Tenant-scoped measurable goals over published Genesis Prime apps.
- Five deterministic metrics: recent record count, numeric min/max/average, and count below threshold.
- Timestamped measurements and strategy proposal/decision history.
- Optional local Ollama hypotheses; AI does not query SQL, modify records, or execute workflows.
- Owners approve/reject strategies; editors propose and snapshot; viewers read.
- Data sampled from the most recent 500 records per app. Metrics are descriptive, not complete historical business analytics.

## Limitations

V25 does not automatically generate or execute V22 workflows, infer profits, prove causality, or provide production-ready multi-tenant SaaS security. Test in local mode before exposing to customers. Database and app files are not bundled. No automatic schema migration of older business records.

## Tests

`python -m unittest -v test_nexus_v25.py`
