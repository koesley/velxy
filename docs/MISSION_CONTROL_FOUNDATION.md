# VELXTRIA Mission Control — foundation milestone

Mission Control is an authenticated, read-only operational view available at
`/mission-control` when `VELXTRIA_ENABLE_BUSINESS_OS_V59=1`.

## Data flow

- The existing portal session and workspace membership select the workspace.
- `mission_control.snapshot` checks access before reading.
- `business_os_v59.overview` provides user-entered sales metrics and approvals.
- `business_agents_v59.overview` provides human-created agent task queues.
- `mission_control.render` escapes all untrusted strings and provides links to
  the existing approval screens. No new database tables or outbound integrations
  are needed.

## Security and boundaries

Mission Control does not run an LLM, generate proposals, send emails, execute
workflows, or prove collected revenue. It inherits the existing 300-lead and
200-agent-job display limits, so counts are not guaranteed to represent all
historical records. Workspace access is enforced independently of navigation.
Existing agent and sales approval endpoints remain the only mutation paths.

## Validation

Run `python -m unittest test_mission_control -v`. The existing V59 validation
workflow includes these tests. No production deployment is authorized by this
milestone.

## Next cohesive milestone

Build a persistent, tenant-scoped job orchestration layer with idempotency
keys, leases, retries, state transitions, operator approvals, and an immutable
audit trail. Integrate it with the existing agent queues before adding external
connectors or AI-generated business actions.
