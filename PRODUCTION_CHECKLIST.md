# DipIFR Mastery Lab — Production Checklist

## Verified statically
- 35 syllabus/standard areas are present in `backend/app/data/standard_catalog.json`.
- 44 supplied historical questions are present across 11 historical rounds.
- Past-round mocks are seeded as fixed 4-question / 100-mark / 195-minute exams.
- Question Bank exposes source round and question number.
- Cross-standard question links are persisted through `QuestionStandardLink`.
- Access tokens are kept in memory on the frontend; refresh tokens use HttpOnly cookies.
- Production runtime validation rejects the default secret, SQLite, and localhost CORS settings.
- Python source parses successfully with `ast.parse`.
- JSON seed files parse successfully.

## Environment limitation
The execution environment used for this audit has no network access. Therefore npm/pip cannot download missing dependencies, so a full production build and full pytest run must be performed after dependencies are installed locally/CI.

## Before GitHub/Vercel
1. `pip install -r backend/requirements.txt`
2. `pytest -q backend/tests`
3. `cd frontend && npm install && npm run typecheck && npm run lint && npm run build`
4. Configure production `SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`, `FRONTEND_URL`, and `NEXT_PUBLIC_API_URL`.
5. Use PostgreSQL in production.
6. Run the supplied historical materials only where their permitted/licensed use allows it.
