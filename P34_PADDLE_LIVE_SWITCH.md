# Core Factory Cloud — Paddle Live Switch

Required Render environment:
- `PADDLE_ENVIRONMENT=live`
- `PADDLE_API_KEY=<Live server API key>`
- `PADDLE_WEBHOOK_SECRET=<Live notification destination secret>`
- `PADDLE_PRICE_CORE_CREDIT_200=<Live pri_...>`
- `PADDLE_PRICE_CORE_CREDIT_500=<Live pri_...>`
- `PADDLE_PRICE_CORE_CREDIT_1200=<Live pri_...>`
- `PADDLE_PRICE_CORE_CREDIT_3500=<Live pri_...>`
- `PADDLE_PRICE_CORE_CREDIT_8000=<Live pri_...>`

Cloud selects `https://api.paddle.com` in Live and fails closed on an obvious
Sandbox/Live API-key mismatch. Payment fulfillment remains webhook-authoritative
and uses the canonical CreditOrderService.
