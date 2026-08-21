# DipIFR Mastery Lab

A production-oriented DipIFR learning workspace with a real question bank,
adaptive practice, timed mock exams, persisted mastery, an AI tutor,
exam-focused IFRS/IAS reference content, and full account management (register/login/refresh/logout/forgot-password/email
verification).

## Product principles
- Fixed-format mock exams are not adaptive to the student's current level.
- Adaptive selection is used for practice and learning recommendations only.
- Cross-standard questions are a first-class learning mode.
- Each authenticated user has private progress and can resume later.
- Official IFRS/IAS standards remain the authoritative source; this platform is a learning aid.

## Stack
- Frontend: Next.js 15 + TypeScript
- Backend: FastAPI + SQLAlchemy
- Database: SQLite for local development; PostgreSQL-ready through `DATABASE_URL`
- Auth: short-lived JWT access tokens (kept in memory on the frontend, never localStorage) + rotating refresh tokens delivered as an HttpOnly/Secure/SameSite cookie (never in a JSON body), Argon2 password hashing
- AI: server-side Anthropic API integration for the tutor and answer grading
  (optional — falls back to keyword-based grading and a static tutor message
  if `ANTHROPIC_API_KEY` isn't set)

## Features
- **Question bank & auto-grading** — real seeded questions per IFRS/IAS topic.
  Answers are graded either by AI (if configured) or by a transparent
  keyword-rubric fallback, and feed back into per-topic mastery.
- **Mock exams** — fixed-format, timed exams composed from the question bank, with server-side ownership checks, expiry enforcement, weighted scoring by marks, and mastery updates after completion.
- **Adaptive practice** — always serves a question from the student's current
  weakest topic.
- **AI Tutor** — free-text Q&A backed by a server-side AI call; the API key never reaches the frontend. Claude Sonnet 4.6 is supported when configured.
- **Accounts** — register, login, silent token refresh with rotation, logout, forgot/reset password, and email verification. Password-reset and verification links are opaque, hashed server-side, expire, and are single-use. The refresh token is set by the server as an HttpOnly cookie (`REFRESH_COOKIE_NAME`, default `dipifr_refresh_token`) scoped to `/auth`; client-side JavaScript never has access to it, so it cannot be exfiltrated by an XSS payload. The access token lives only in an in-memory variable on the frontend and is silently re-derived from the refresh cookie on page load via `restoreSession()`.

## Local development

### Backend
```bash
cd backend
python -m venv .venv
# activate the environment
pip install -r requirements.txt
cp .env.example .env   # then edit SECRET_KEY, and optionally ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```
The question bank and mock exams are seeded automatically on first startup.

Run the test suite:
```bash
pytest -v
```

### Frontend
```bash
cd frontend
npm install
npm run typecheck
npm run lint
npm run build
npm run start
```

Set `NEXT_PUBLIC_API_URL` when connecting the frontend to the backend (see
`frontend/.env.example`).

## Security
- Never commit real `.env` files, API keys, database passwords, or production secrets.
- `SECRET_KEY` must be set to a long random value before running with `ENVIRONMENT=production` — the app refuses to start otherwise.
- Auth endpoints are rate-limited; the in-memory limiter is fine for a single instance but should move to Redis-backed storage before scaling to multiple workers.
- If the frontend and backend are deployed on different sites (e.g. Vercel + a separate API host), set `REFRESH_COOKIE_SAMESITE=none` on the backend — a `Lax` cookie is not attached to cross-site `fetch()` calls, only to top-level navigations. `SameSite=None` requires HTTPS, which `cookie_secure` enforces automatically outside `development`/`test`.
- Email sending is currently a `ConsoleEmailSender` stub that logs verification/reset emails instead of delivering them (see `backend/app/core/email.py`) — no real provider (SES/Postmark/SendGrid/etc.) is wired up yet, and there is no `EMAIL_API_KEY` in use despite being referenced in the original spec. Verification and password-reset links will not reach real users until a provider is implemented behind the existing `EmailSender` interface.


## Engineering notes
- The application is intentionally split into `frontend/` and `backend/`; Vercel should deploy only `frontend/`.
- Production requires PostgreSQL, a random `SECRET_KEY` of at least 32 characters, explicit production CORS origins, and provider-managed secrets.
- Mock exams are fixed by design. Adaptive behaviour is applied to practice and mastery updates, not to the exam blueprint.
- The fallback grader is a transparent development fallback, not an ACCA-certified marking engine.
- Before public launch, run dependency auditing and upgrade the locked frontend dependencies to the latest supported security patch.


## Content coverage

This build includes a syllabus-aligned catalog for the current DipIFR study guide, including IFRS 18 and IFRS 19, plus original practice questions, cross-standard questions, and indexed historical rounds from the user-provided exam compilation. Each question carries a source and, where applicable, a historical round/question number. The official ACCA syllabus and past-exam pages are retained as source references.

Official references: https://www.accaglobal.com/uk/en/student/exam-support-resources/dipifr-study-resources/dipifr-syllabus-study-guide.html and https://www.accaglobal.com/middle-east/en/student/exam-support-resources/dipifr-study-resources/past-examinations.html
