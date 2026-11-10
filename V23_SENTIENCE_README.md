# VELXTRIA V23 — Project Sentience (first milestone)

Adds `/sentience` to the local SQLite studio. This release provides **deterministic tenant-scoped analysis** of the 500 most recent records per application, numeric field minimum/maximum/average, reviewable recommendations, and owner-approved conversion into **draft** V22 Autonomy rules. Owners must separately activate drafts in Autonomy.

## Run
Back up the existing SQLite database. Keep `VELXTRIA_DATA_DIR` pointing to the same data directory. Set `VELXTRIA_LOCAL_STUDIO=1`, `VELXTRIA_DEPLOYMENT_MODE=local`, then run `python portal.py` and visit `http://127.0.0.1:8878/sentience`.

## Tests
`python -m unittest -v test_sentience_v23`

## Scope and limitations
No Ollama integration, free-form chat, forecasting, autonomous action execution, or external notifications in this milestone. Statistics are descriptive, not profit forecasts. Tenant isolation applies to V23's queries and proposals; legacy modules may not be tenant-aware. Local development only; not security-audited for public multi-tenant deployment. Docker and full browser workflow were not tested here. The V22 rule creation requires a published application with a numeric field. AI-generated SQL and code are not executed.
