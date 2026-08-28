# Core Factory 3.4.x — Paddle Auto Payment Foundation

## Invariant
Paddle never grants Core Credits. `transaction.completed` is verified, resolved and validated, then calls the same `CreditOrderService.confirm_order()` used by manual approval.

## Cloud environment
- `PADDLE_ENVIRONMENT=sandbox` (change to `live` after approval)
- `PADDLE_API_KEY=...` (server secret)
- `PADDLE_WEBHOOK_SECRET=...` (notification destination secret)
- `PADDLE_WEBHOOK_TOLERANCE_SECONDS=300`
- `PADDLE_PRICE_CREDIT_STARTER_100=pri_...`
- `PADDLE_PRICE_CREDIT_BUILDER_250=pri_...`
- `PADDLE_PRICE_CREDIT_CREATOR_600=pri_...`
- `PADDLE_PRICE_CREDIT_PRO_1750=pri_...`
- `PADDLE_PRICE_CREDIT_POWER_4000=pri_...`

## Paddle dashboard
Create five one-time prices matching the authoritative Cloud snapshots: 200/$5, 500/$10, 1200/$20, 3500/$50, 8000/$100 USD. Put their `pri_...` IDs in Cloud env vars.

Set the approved website default payment link to the deployed `/payment.html` page. The landing deployment must set its PUBLIC Paddle client-side token in `payment-config.js`. Never put API keys or webhook secrets in landing/Core.

Notification destination:
`https://ecosystem-verify-server.onrender.com/v1/cloud/payments/paddle/webhook`

Subscribe at minimum to `transaction.completed`. The handler verifies `Paddle-Signature` over the raw body, validates Core order/account/package/price/currency/subtotal, then calls canonical confirmation.

## Core API
1. Existing create order → PENDING.
2. POST `/v1/cloud/credit-orders/checkout` with active Core credentials + `order_id`.
3. Open returned `checkout_url` in browser.
4. Paddle webhook completes fulfillment asynchronously.
5. Core refreshes existing Wallet endpoints; no Wallet redesign.

## Acceptance
Test duplicate webhook, invalid signature, wrong price/package/currency/amount, manual-before-auto, auto-before-manual, unknown order, and normal completed checkout. All must preserve one CreditGrant per order.
