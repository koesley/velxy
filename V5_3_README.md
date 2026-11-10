# VELXTRIA V5.3 — Mission-specific execution

## Install locally

1. Back up your **existing** `portal.sqlite3` and any external `VELXTRIA_DATA_DIR` before changing code.
2. Stop the running server. Extract this ZIP and open `velxy-main` in Cursor.
3. If your data directory was inside your old project, copy your original `portal.sqlite3` into the new folder **while the server is stopped**. Do not overwrite an existing populated database. If `VELXTRIA_DATA_DIR` is set, retain that value instead.
4. Preserve your local environment variables and run `python portal.py`.
5. Visit `/missions`, create or open a mission, then select **Open mission-specific proposals and execution**.

## What's implemented

- Scans are mission-specific, based on clear customer/lead or website keywords in mission title/objective. No paid AI interpretation.
- Lead missions prepare one **internal** follow-up draft per eligible account-wide lead/qualified contact. Approve, then Execute to persist the draft and log it; no email is sent and CRM stage is unchanged.
- Website missions prepare private draft headline changes for websites owned by the signed-in user. Approve, then Execute to update the private draft; you can view the preview and restore the previous headline if no later edit has replaced it.
- Every proposal and execution belongs to a specific mission. Old V5.2 and V5.1 history is retained.
- Mission progress uses mission-specific executed actions, not account-wide logs.

## Known limits

- CRM records are scoped to the signed-in account, not yet individually associated with Gerate or another company. **Do not treat this as company-level CRM isolation.**
- Drafts are templates, not AI-generated personalized outreach; human review and consent checks remain necessary.
- No automatic scheduling, emails, public website publishing, purchases, or external API calls.
- Existing V5.1 generic Business Operator proposals remain visible on its separate page.
- No production deployment is intended; test locally before considering any hosted use.
