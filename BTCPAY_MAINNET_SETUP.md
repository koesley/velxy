# VELXTRIA BTCPay Mainnet Setup

Production Bitcoin payments for VELXTRIA PRO: **$49 USD / 30 days / 50 reports**,
paid in Bitcoin through BTCPay Server. The testnet integration
(`btcpay_integration.py`) is unchanged and stays separate for development.

## How it works

- Customer clicks **Pay $49 with Bitcoin** on the dashboard or Account page
  (`POST /btcpay/mainnet/checkout`). The app creates a BTCPay invoice for
  $49.00 USD and redirects the customer to the BTCPay checkout page.
- The customer pays in Bitcoin. Nothing is activated from the browser
  redirect.
- PRO is granted only after the app re-reads the invoice from BTCPay and
  confirms: invoice id matches the order, metadata order id matches,
  amount is exactly $49.00, currency is USD, and status is `Settled`.
- Two triggers re-verify: loading the dashboard / Account page, and the
  BTCPay webhook (`POST /webhooks/btcpay`). The webhook is HMAC-SHA256
  signature-verified and is only a trigger — the payload is never proof.
- Settlement is idempotent: a settled invoice is claimed exactly once
  (conditional `UPDATE ... WHERE status='pending'`), so duplicate checks,
  duplicate webhooks, and concurrent reconciles can never extend a
  subscription twice.
- Expired / Invalid invoices are recorded as such and grant nothing. A
  refunded invoice never grants access. A refund *after* settlement must
  be revoked by the operator (see below).

## Environment variables (Render only)

Set these in the Render dashboard. Never commit values, never paste them
in chat, never print them in logs.

| Variable | Value |
| --- | --- |
| `VELXTRIA_BTCPAY_MAINNET_URL` | Production BTCPay Server URL, e.g. `https://btcpay.example.com` |
| `VELXTRIA_BTCPAY_MAINNET_STORE_ID` | BTCPay store ID (see below) |
| `VELXTRIA_BTCPAY_MAINNET_API_KEY` | Greenfield API key (see below) |
| `VELXTRIA_BTCPAY_MAINNET_WEBHOOK_SECRET` | Secret you invent for the webhook (see below) |
| `VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT` | `0` until verified, then `1` |

> The flag is dashboard-controlled: `render.yaml` declares it with
> `sync: false` and no value. Never declare a value for it in
> `render.yaml` — a declared `value: '0'` is re-applied on every
> blueprint sync and silently turns checkout back off, even after it
> was switched on in the dashboard and verified live (this happened
> on 2026-11-18: the flag was set to `1` and a real invoice created,
> then a later deploy reset it to `0`).

The testnet variables (`VELXTRIA_BTCPAY_URL`, `VELXTRIA_BTCPAY_STORE_ID`,
`VELXTRIA_BTCPAY_API_KEY`, `VELXTRIA_ENABLE_BTCPAY_TEST_CHECKOUT`) are
separate and are for local development only.

## 1. Locate the store ID

1. Log in to your BTCPay Server and open the store you will take payments in.
2. Go to **Store Settings** (or **Settings**) for that store.
3. The **Store ID** is shown on the settings page. It is also the segment
   after `/stores/` in the browser address bar while you are in that store.
4. Copy it into `VELXTRIA_BTCPAY_MAINNET_URL`'s companion variable
   `VELXTRIA_BTCPAY_MAINNET_STORE_ID` in Render.

## 2. Generate a Greenfield API key

1. In BTCPay, open the account menu (top right) → **API Keys** → **Create
   new API key** (wording varies slightly by BTCPay version).
2. Select the store from step 1.
3. Tick exactly these permissions:
   - `btcpay.store.cancreateinvoice` — create $49 invoices
   - `btcpay.store.canviewinvoices` — read invoice status for verification
   - `btcpay.store.canviewstoresettings` — read the BTC payment method for
     the mainnet support check
4. Generate the key and copy it **once** — BTCPay shows it only at creation.
5. Paste it into `VELXTRIA_BTCPAY_MAINNET_API_KEY` in Render. Do not paste
   it anywhere else.

## 3. Create the webhook

1. In the same store, go to **Store Settings → Webhooks → Create webhook**.
2. Payload URL: `https://<your-render-host>/webhooks/btcpay`
   (e.g. `https://velxtria-private-preview.onrender.com/webhooks/btcpay`).
3. Secret: generate a long random string (e.g. 32+ characters). This exact
   string becomes `VELXTRIA_BTCPAY_MAINNET_WEBHOOK_SECRET` in Render.
4. Tick these events: **Invoice received payment**, **Invoice payment
   settled**, **Invoice expired**, **Invoice invalid**.
   (BTCPay may also list them as `InvoiceReceivedPayment`,
   `InvoicePaymentSettled`, `InvoiceExpired`, `InvoiceInvalid`.)
5. Save. BTCPay will send a test ping on save; the app answers 200 only
   for signature-verified deliveries naming a known invoice, and 401 for
   anything else.

## 4. Add the variables in Render

1. Render dashboard → service **velxtria-private-preview** → **Environment**.
2. Add each variable from the table above (name + value), then **Save
   Changes**. Render redeploys automatically.
3. Keep `VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT` at `0` until step 5
   passes.

## 5. Confirm the server supports real mainnet payments

The code refuses testnet hosts in mainnet mode. BTCPay's official mainnet
demo (mainnet.demo.btcpayserver.org) is a real mainnet instance and is
allowed. The URL alone cannot prove the store is on mainnet, so run both
checks:

**A. Automated check (no funds spent, no invoice created):**

```sh
python btcpay_mainnet.py --check
```

Expected output: `ok=True`, `btc_enabled=True`, and the production host.
It confirms the server is reachable, the store and key work, and the BTC
payment method is enabled. It does not confirm mainnet by itself.

**B. Manual dashboard check (decisive):**

1. In BTCPay, open the store → **Store Settings → Payment methods**.
2. The on-chain **BTC** method must be enabled and show **Mainnet**.
   A testnet store shows **Testnet** instead.
3. The store's BTC receiving addresses must start with `bc1q` (mainnet
   bech32). Testnet addresses start with `tb1q`. If you see `tb1q`, the
   store is testnet — do not enable checkout.

Only when both checks pass, set
`VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT` to `1` in Render.

## 6. Verify deployment and a real invoice — without paying

1. Merge the `btcpay-mainnet` branch to `main`. Render redeploys.
2. `GET /healthz` returns `200 ok`. The dashboard loads; with the flag at
   `0` it still shows the manual-arrangement panel.
3. Set the flag to `1` (after step 5). The dashboard and Account page now
   show **Pay $49 with Bitcoin**.
4. As a test customer, click it. You are redirected to a real BTCPay
   checkout page showing **$49.00 USD** for "VELXTRIA PRO - 30 Days -
   50 Reports". **Do not pay.**
5. On the Account page the order shows **pending** with a link back to the
   checkout. Leave it unpaid: the invoice expires on its own, and the
   account shows **expired** with no PRO granted. That proves the full
   create → pending → expire path without spending funds.
6. Full settlement activation (pay → PRO active) still needs one real
   $49 payment. It is covered by automated tests
   (`test_btcpay_mainnet.py`), but it has not been exercised against the
   live server — do not claim payments work until that live payment test
   is done.

## Refunds and operator actions

- BTCPay sends no invoice-refund webhook event. If a customer is refunded
  after settlement, revoke access with the existing operator CLI (the
  subscription itself is untouched by any webhook):

```sh
python subscription_admin.py revoke --email <customer@example.com> \
  --note "Refunded via BTCPay, invoice <invoice-id>" --confirm-verified
```

- A refund recorded before settlement verification means the invoice is
  never treated as settled, so no access is granted in the first place.
- `subscription_admin.py activate` (manual Stripe/Payhip flow) is
  unchanged and still works.

## Tests

```sh
python -m unittest test_btcpay_mainnet -v
```

25 tests, mocked BTCPay API, no credentials, no network. Covers: successful
payment, expired/invalid/processing invoices, wrong amount / currency /
order / invoice id, refunded invoices, repeated reconciliation
(idempotency), cross-user activation attempts, webhook signature
verification, duplicate webhook deliveries, webhook payloads that lie
about settlement, and the mainnet support check.
