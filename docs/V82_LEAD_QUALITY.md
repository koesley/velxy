# VELXTRIA V82 — Lead Quality Inspector

A read-only CRM data-quality inspector. It identifies invalid email contacts, missing names, unexpected statuses, and duplicate email contacts within a bounded sample. It never deletes, merges, or edits leads.

Run: `python -m unittest -v test_lead_quality_v82.py`

## Production work
Authenticate and authorize the workspace before calling the inspector. Integrate it into the owner dashboard, use cursor-based pagination for full datasets, provide reviewed merge workflows with audit and rollback, and test PostgreSQL/SQLite compatibility. The current inspector is standalone, and duplicate detection is limited to the sampled rows. Do not represent the output as a complete database-wide audit.
