# Payment-to-access integration: verified state and production blockers

## Existing architecture
- `subscriptions.entitlement` grants PRO only for an independently verified,
  unexpired subscription period.
- `btcpay_integration.reconcile` performs authenticated provider-side GETs,
  validates invoice ID, order metadata, amount, currency and Settled status,
  conditionally claims a pending invoice once, and updates the subscription.
- BTCPay is intentionally **testnet only**; this is not real-money billing.
- `payhip_integration.accept_event` records Payhip notifications for review.
  The documented signature is a SHA256 of the API key, not a per-event body
  HMAC. An event alone cannot safely grant access.
- `license_verification.verify` independently validates a Payhip product
  license against Payhip, but that one-time license is not equivalent to a
  verified recurring subscription period.

## This milestone
- Authenticated `GET /billing/status` reconciles the signed-in user's
  pending **testnet** invoices and reports the effective entitlement,
  pending count and provider check state. The endpoint uses no-store.
- The account page also reconciles before displaying entitlement and links
  to the status endpoint.
- Regression tests cover verified activation, retries, invalid invoice
  state, wrong amount, wrong order and cross-user isolation.
- The existing home page already reconciled testnet invoices; the account
  and billing status paths now share that behavior.

## Production blockers — do not market as live paid activation
1. Choose and configure a **production** payment provider supporting
   authenticated, transaction-bound payment verification and subscription
   lifecycle queries. Do not remove BTCPay's testnet guard to simulate this.
2. Establish a verified mapping from provider customer/subscription IDs to
   a VELXTRIA user without trusting email-only webhook claims.
3. Implement authenticated provider event ingestion, durable idempotent
   event processing, missed-event reconciliation and full lifecycle handling
   (renewals, cancellation, expiry, refunds, chargebacks).
4. Implement a real billing UI and integration tests against provider sandbox
   credentials before enabling production access.
5. Do not conflate Payhip one-time license verification with recurring PRO
   subscription entitlements.

No production deployment, merge, provider configuration or real charge
is performed by this milestone.
