# DipIFR Mastery Lab — Production Checklist

## Verified with a full install + test run (2026-09-05)
- `pip install -r backend/requirements.txt` succeeds; `pytest -q` → **75 passed**.
  - Fixed: `backend/app/api/auth.py` was truncated mid-function in source control
    (the file ended inside `refresh()` with a bare `raise`). `/auth/refresh`,
    `/auth/logout`, `/auth/password/forgot`, `/auth/password/reset`,
    `/auth/verify-email`, and `/auth/resend-verification` did not exist as
    routes, so every request to them 404'd — this was very likely the root
    cause of the previously-reported broken deployment. All six endpoints
    have been implemented (refresh rotation + revocation, logout revocation,
    generic-response forgot/reset, single-use verify/reset tokens) and are
    now covered by the existing test suite.
- `cd frontend && npm install && npm run typecheck && npm run lint && npm run build` all succeed with zero errors.
  - Removed stray duplicate/backup page files that were committed by mistake
    and not referenced anywhere (`frontend/app/page.tsx.tsx`, `page_2.tsx`,
    `page_3.tsx`, `page_6.tsx`, and a duplicate root-level `page.tsx.tsx` /
    `globals.css`). Only `frontend/app/page.tsx` was ever live; the rest were
    dead weight and the source of a misleading extra lint warning.
  - Fixed the one real lint warning (missing `useEffect` dependency in the
    Question Bank component) with an explicit, documented exclusion.
- 35 syllabus/standard areas are present in `backend/app/data/standard_catalog.json`.
- 44 supplied historical questions are present across 11 historical rounds.
- Past-round mocks are seeded as fixed 4-question / 100-mark / 195-minute exams.
- Question Bank exposes source round and question number.
- Cross-standard question links are persisted through `QuestionStandardLink`.
- Access tokens are kept in memory on the frontend; refresh tokens use HttpOnly cookies.
- Production runtime validation rejects the default secret, SQLite, localhost CORS, and missing SMTP settings.
- `backend/.env.example` now lists every variable `config.py` actually reads (SMTP/email, Gemini, admin key were previously missing from it).

## Known remaining item (not fixed here — needs a maintainer decision)
- `npm audit` reports 5 advisories (3 high) in build-time tooling
  (`postcss`/`sharp`, pulled in transitively by Next.js, and `eslint`'s
  plugin-kit). The fix requires upgrading to `next@16`, which is a breaking
  major-version change — not applied automatically here to avoid introducing
  untested regressions. Plan a dedicated Next 16 upgrade + regression pass
  before relying on `npm audit fix --force`.

## Before GitHub/Vercel/Railway
1. `pip install -r backend/requirements.txt && pytest -q backend/tests` — done above, passing.
2. `cd frontend && npm install && npm run typecheck && npm run lint && npm run build` — done above, passing.
3. Configure production `SECRET_KEY` (random, ≥32 chars), `DATABASE_URL` (PostgreSQL), `CORS_ORIGINS`, `FRONTEND_URL`, and `NEXT_PUBLIC_API_URL`.
4. Configure `SMTP_HOST` + `SMTP_FROM_EMAIL` (+ `SMTP_USERNAME`/`SMTP_PASSWORD`) so verification/reset emails actually reach users — the app intentionally refuses to boot in production without these.
5. Redeploy the Railway backend service and confirm `GET /health` (and now `GET /`) return 200 — the previously reported 404 at the Railway URL was caused by the missing auth routes above plus (possibly) a stale/incomplete deploy; redeploying from the fixed `main` branch should resolve it.
6. Use PostgreSQL in production.
7. Run the supplied historical materials only where their permitted/licensed use allows it.
