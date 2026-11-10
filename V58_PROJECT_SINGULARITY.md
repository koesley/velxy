# VELXTRIA V58 — Project Singularity (first working milestone)

This release adds a **standalone software factory**, not a new dashboard. `singularity_factory_v58.py` accepts a strict JSON specification and produces an independent Python/SQLite CRM with a browser interface, CRUD API, automated tests, SHA-256 file manifest and distributable ZIP.

## Run

```powershell
python singularity_factory_v58.py --output my_generated_crm
cd my_generated_crm
python -m unittest -v
python app.py 8891
```

Open http://127.0.0.1:8891. To customize the generated application, save `{"name":"My CRM","fields":["name","email","company","status"],"variant":"standard"}` as `spec.json`, then run `python singularity_factory_v58.py --spec spec.json --output my_other_crm`.

`--compare` builds both currently supported variants and reports verification, source size, and build time. The variants are currently functionally equivalent and are **not** an evolutionary code-search engine.

## Boundaries

- No LLM or natural-language generation. Only an allowlisted CRM specification is supported.
- No arbitrary generated code execution from user-supplied source; the generator runs its own trusted test template in a subprocess with a 20-second timeout. **A timeout is not a security sandbox**.
- Generated app binds only to 127.0.0.1, but has no authentication or CSRF protection. Do not expose it to the internet or use sensitive production data.
- The source manifest provides checksums for generated files, not cryptographic signing or a proof of correctness.
- The generated app supports CRUD and basic validation, not production-grade tenancy, encryption, or integrations.
- Back up the V57 database before upgrading; the V58 factory does not modify the existing V57 database.

## Next engineering gate

A genuine natural-language software generator needs a connected code model, strict sandboxing (OS-level isolation, limits, disabled network), independent tests, vulnerability checks, approval gates and rollback. None of those are claimed in this release.
