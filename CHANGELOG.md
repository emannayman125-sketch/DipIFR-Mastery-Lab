# Engineering Review & Fixes

## Security (this session)
- Moved the refresh token out of the JSON response body and localStorage entirely; it is now set by the backend as an HttpOnly, Secure (outside dev/test), SameSite cookie scoped to `/auth` and is never readable by client-side JavaScript.
- Access token is now held only in an in-memory variable on the frontend (not localStorage/sessionStorage); a new `restoreSession()` silently exchanges the refresh cookie for a fresh access token on page load.
- Added `REFRESH_COOKIE_SAMESITE` setting (`lax` by default, `none` for cross-site frontend/backend deployments) and production validation for it.
- Added the `backend/.env.example` and `frontend/.env.example` files referenced by the README but missing from the repo.
- Documented that the email system is currently a console-logging stub with no real provider wired up (no `EMAIL_API_KEY` in use) — verification/reset emails do not reach real users yet.

## Security
- Replaced reusable JWT email-verification/password-reset links with hashed, opaque, single-use tokens.
- Added atomic refresh-token rotation to reduce concurrent replay risk.
- Added production validation for secret length, database type, and CORS configuration.
- Added root `.gitignore` to prevent secrets, databases, build output and dependencies from being committed.
- Kept AI credentials server-side only.

## Exam integrity
- Added server-side exam expiry.
- Added server-side question-to-exam authorization checks.
- Added unique `(attempt_id, question_id)` constraint for exam answers.
- Changed final scoring to be weighted by question marks rather than answer count.
- Completed mock exams now update the same mastery engine used by adaptive practice.
- Added a visible countdown timer in the exam UI.

## Learning experience
- Expanded the Knowledge Base with exam-focused explanations, key rules, practice focus and scenarios for the seeded standards.
- Improved adaptive dashboard continuity and kept mock exams fixed rather than silently changing their blueprint.

## Engineering / deployment
- Added root pytest configuration so tests can be discovered from the repository root.
- Added GitHub Actions CI for backend tests and frontend typecheck/lint/build.
- Migrated frontend linting to the ESLint CLI configuration recommended by current Next.js documentation.
- Updated Next.js to the maintained 15.5 backport line (15.5.22) and removed the stale lockfile so a clean install regenerates dependencies.
- Updated Docker Compose to pass production-relevant backend environment variables.
