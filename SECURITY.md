# Security baseline

## Implemented
- Passwords are hashed with Argon2 through `pwdlib`.
- Access JWTs are short-lived and purpose-scoped.
- Refresh tokens are random opaque values; only SHA-256 hashes are stored and used tokens are rotated/revoked.
- Password-reset and email-verification tokens are random opaque values, stored only as hashes, expire, invalidate older tokens for the same purpose, and are single-use.
- Authenticated routes resolve the current user server-side from the access token.
- Exam attempts are bound to the authenticated user, expire server-side, and reject questions that do not belong to the selected exam.
- CORS is allowlist-based. Production rejects localhost CORS defaults.
- Production rejects insecure/default secrets and SQLite.
- AI provider credentials stay on the backend.
- Auth and tutor endpoints have rate limits.
- `.env` and local databases are excluded from Git.

## Required before public launch
- Use PostgreSQL and Redis-backed rate limiting for multi-instance deployment.
- Replace console email delivery with a transactional email provider.
- Prefer secure HttpOnly/SameSite cookies for browser authentication instead of long-lived tokens in localStorage when the deployment architecture allows it.
- Add dependency scanning, secret scanning, container scanning, structured audit logs, backup/restore testing, and monitoring to CI/CD.
- Keep Next.js and all transitive dependencies on current security releases.
- Treat AI output as advisory; never use it as the sole authority for accounting standards or high-stakes decisions.
