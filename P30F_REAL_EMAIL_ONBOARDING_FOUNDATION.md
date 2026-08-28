# P30F — Real Email Onboarding Foundation

Cloud V2.0 adds email-first Core activation without exposing the email verification token to Local Core.

Flow:

Register email → onboarding session credential returned to Core → verification link delivered by EmailDeliveryAdapter → user clicks Cloud verify-link → Trial + Core entitlement activate → Core checks onboarding session → Cloud registers Core → Core receives core_secret + signed access grant.

Security boundaries:
- verification token is stored hashed and delivered only by email;
- onboarding_secret is an independent opaque credential stored hashed in Firestore;
- onboarding completion requires the verification record attached to that exact onboarding session to be verified;
- an email verified in the past does not silently authorize a new Core activation;
- Core never receives GitHub/storage/payment credentials;
- Trial starts only at email_verified_at.

Production email adapter:
- CLOUD_EMAIL_PROVIDER=smtp
- CLOUD_PUBLIC_BASE_URL=https://ecosystem-verify-server.onrender.com
- CLOUD_SMTP_HOST
- CLOUD_SMTP_PORT (default 587)
- CLOUD_SMTP_USERNAME (optional if provider does not require username)
- CLOUD_SMTP_PASSWORD
- CLOUD_EMAIL_FROM
- CLOUD_EMAIL_FROM_NAME (default Core Factory)
- CLOUD_SMTP_STARTTLS=true|false
- CLOUD_SMTP_SSL=true|false

New endpoints:
- GET /v1/cloud/email/verify-link?token=...
- POST /v1/cloud/onboarding/status
- POST /v1/cloud/onboarding/resend
- POST /v1/cloud/onboarding/complete

Existing /v1/cloud/register remains additive and now returns onboarding_session_id + onboarding_secret + onboarding_expires_at for Local Core.
