# VELXTRIA V29 — Project Integration

A read-only, workspace-scoped customer journey at `/integration`. Requires `VELXTRIA_LOCAL_STUDIO=1` and local SQLite mode.

## What it does
- Guides workspace → published application → saved record → business goal → pilot feedback.
- Reads existing Launchpad evidence and workspace-specific feedback.
- Shows key module table-presence diagnostics (not a functional audit).
- Adds a shortcut in Ascension and the global navigation.

## Limitations
No automated invitations, production deployment, payments, or comprehensive end-to-end browser verification. Database schema presence is not a security certification. Back up the existing SQLite DB before upgrading.

## Test
`python -m unittest test_integration_v29`
