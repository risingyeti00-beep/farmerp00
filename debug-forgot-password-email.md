[OPEN] Forgot Password Email OTP Debug Session

## Session
- session_id: forgot-password-email
- date: 2026-07-22
- symptom: forgot-password API reports success but OTP email does not arrive in recipient inbox on Railway live backend.
- live_backend: https://farmerp-backend-production-bf99.up.railway.app

## Hypotheses
1. Railway runtime is missing one or more `EMAIL_*` environment variables.
2. Gmail SMTP authentication or TLS negotiation fails at send time.
3. Live deployment is not running the latest backend code / Docker image.
4. OTP is generated in DB but email delivery fails after generation.
5. Recipient lookup or user state prevents the correct target email from being used.

## Evidence Plan
1. Inspect current mail configuration loading path in backend settings.
2. Inspect forgot-password endpoint runtime path and logging.
3. Reproduce locally against current code with direct email send.
4. Compare local behavior with live endpoint behavior.
5. Apply minimal fix only after evidence confirms root cause.
