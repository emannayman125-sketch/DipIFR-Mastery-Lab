# Engineering Review & Fixes

## Accounting content accuracy (this session)
- **Removed all verbatim ACCA copyrighted material — found in two separate places.** The 44 "past exam" question records in `backend/app/data/past_exam_questions.json` previously stored ACCA's actual exam question text and their real published suggested answers. A second, previously undiscovered block hardcoded directly in `seed_data.py` (`REAL_SESSION_IAS16_23`, 7 questions on IAS 16/IAS 23 spanning Dec 2017 – June 2023) had the same problem, including full worked model answers reproducing the real exam's specific figures. Both are now replaced with (a) a direct link to the official ACCA past-papers page for that sitting (and the official examiner's report where available), and (b) our own short factual description of the topics the question covers. Grading for all of these now uses our own keyword rubric instead of an AI comparison against a placeholder.
- **Added 4 more real exam sittings as reference-only entries** (June 2023, December 2023, June 2024, December 2024 — 16 questions), closing a ~5-year gap between the platform's most recent sitting (June 2020) and ACCA's current past papers. Topics were sourced from ACCA's own published examiner's reports (which describe what was tested, not the copyrighted question text itself) and are cited with direct links to those reports.
- **Added IAS 7 Statement of Cash Flows**, a significant syllabus gap — it is one of the most consistently examined topics in the real DipIFR exam and was previously entirely absent from the platform.
- **Added IFRS 1 First-time Adoption**, which is on the official examinable syllabus but was missing. Given a full 25-mark flagship question would misrepresent how rarely IFRS 1 appears as a standalone question in the real exam, it instead has a proper scenario-level (10-mark) question, and the syllabus-coverage test documents this deliberately.
- **Flagged IFRS S1/S2 (ISSB sustainability standards) as not examinable** in the ACCA DipIFR syllabus (new `examinable` field on `Standard`, surfaced in the UI). Replaced a full 25-mark flagship question that had been built around IFRS S1 — occupying a quarter of a mock exam with non-examinable content — with a new, properly integrated IAS 7 flagship question instead.
- Fixed the standard-tagging logic for legacy past-exam questions, which previously matched against the (now-removed) copyrighted question text; it now matches against our own retained topic keywords.


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
