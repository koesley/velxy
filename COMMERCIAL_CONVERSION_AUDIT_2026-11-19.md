# VELXTRIA commercial conversion audit — 2026-11-19

## Verified repository observations
- Render starts `python portal.py` and uses `/healthz` as its health check (render.yaml).
- `portal.py` currently presents a large number of primary navigation links, including repeated labels. This makes the main commercial journey difficult to distinguish from internal feature exploration.
- The public site description describes a sales-CSV reporting product with a free demo and PRO at $49/30 days, Bitcoin only.
- `test_signup_path.py` covers registration, login redirects, and session-cookie issuance.
- `subscriptions.py` grants PRO only for independently verified active subscriptions; webhook claims alone do not grant access.
- BTCPay checkout activation is controlled by a Render environment variable, not the repository blueprint.

## Commercial blockers to validate next
1. Confirm public preview access and whether the preview password prevents prospective customers from reaching the demo.
2. Complete a browser journey: landing → free sample → registration → PRO checkout → payment confirmation → entitled account.
3. Check whether a prospective customer understands the offer, price, payment method, and deliverable within 30 seconds.
4. Verify pricing and checkout states in both enabled and disabled modes, without changing production payment flags.
5. Capture funnel metrics: landing visits, demo completions, registration completions, checkout starts, independently verified purchases.

## First release acceptance criteria
- A first-time visitor can find one prominent free-demo action and one clearly priced paid action.
- Existing registration, session, CSRF, and verified-entitlement safeguards remain intact.
- Payment status is never inferred from an unverified webhook.
- Tests cover both payment-enabled and disabled states.
- A live deployment is only reported after the actual Render URL is checked.

## Customer acquisition experiment
Offer a 15-minute demo to 20 relevant service businesses. Track contacted, replied, demoed, trialed, and paid, plus specific objections. Do not treat hypothetical interest as revenue.

## Execution rule
Ship a focused, tested customer-conversion change next. Do not introduce new disconnected AI modules until the existing purchase journey has been verified.
