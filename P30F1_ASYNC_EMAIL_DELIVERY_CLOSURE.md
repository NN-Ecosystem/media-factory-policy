# P30F.1 Async Email Delivery Closure

Registration persistence is decoupled from SMTP latency. `POST /v1/cloud/register` creates the pending user/verification/onboarding session, returns immediately with `email_delivery.state=queued`, and schedules verification email delivery through FastAPI BackgroundTasks. SMTP/provider failure is logged and does not destroy the pending onboarding state. The existing resend endpoint remains available.

This closes the observed Core UI read timeout while `/health` stayed healthy. Trial still starts only on verification.
