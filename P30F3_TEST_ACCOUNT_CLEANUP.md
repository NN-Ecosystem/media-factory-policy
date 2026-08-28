# P30F.3 — Test Account Cleanup Utility

Adds a guarded administrative script for resetting a Cloud Foundation test account so the same real email can be used for a clean fresh-install onboarding acceptance test.

## Command

Preview only (default):

```powershell
python scripts\cloud_delete_test_account.py --email "tester@example.com"
```

Delete after reviewing the preview:

```powershell
python scripts\cloud_delete_test_account.py --email "tester@example.com" --confirm
```

The script requires `FIREBASE_CRED` in the environment, or accepts `--firebase-cred-file <service-account.json>`.

## Cloud Foundation records removed

- `cloud_users/<user_id>`
- `cloud_user_emails/<sha256(normalized_email)>`
- `user_trials/<user_id>`
- `entitlements` for `subject_id == user_id`
- `core_registrations` for `user_id == user_id`
- `cloud_onboarding_sessions` for `user_id == user_id`
- `email_verifications` for `user_id == user_id`

Audit events are retained by default. `--include-audit` is available only for intentional test cleanup.

## Safety

- Dry-run by default.
- Exact email is normalized and resolved through the email index.
- User/email mismatch stops deletion.
- Dependent records are deleted before the identity/index.
- The script performs a post-delete lookup and returns `RESULT cleanup_complete` only when the account graph is gone.

This is an administrative/test utility. It is not exposed as a public HTTP endpoint.
