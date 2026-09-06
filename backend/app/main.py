import logging 
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from .core.config import settings
from .core.limiter import limiter
from .db import Base, engine, SessionLocal
from sqlalchemy import inspect, text
from .api.auth import router as auth_router
from .api.learning import router as learning_router
from .api.exams import router as exams_router
from .api.tutor import router as tutor_router
from .api.content import router as content_router
from .api.admin import router as admin_router
from .models import User, TopicProgress, PracticeAttempt, RefreshToken, Question, MockExam, MockExamQuestion, ExamAttempt, ExamAnswer, Standard, Topic, LearningResource, PastExamSession, QuestionStandardLink, QuestionCriterion
from .seed_data import seed_if_empty
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")
def _apply_lightweight_column_migrations(engine) -> None:
    """`Base.metadata.create_all` only creates tables that don't exist yet —
    it never alters an existing table, so adding a new column to a model
    (like `Standard.examinable`) does nothing on a database that already has
    that table. Without a real migration tool (Alembic) in this project,
    this checks for a small, known list of columns added after the initial
    schema and adds any that are missing, so existing production databases
    don't crash on startup after a model change. New tables are still
    handled fine by create_all above; this only covers ALTER TABLE ADD COLUMN
    on tables that may already exist."""
    inspector = inspect(engine)
    if not inspector.has_table("standards"):
        return  # fresh database — create_all above already added the column
    existing_columns = {col["name"] for col in inspector.get_columns("standards")}
    if "examinable" not in existing_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE standards ADD COLUMN examinable BOOLEAN DEFAULT TRUE NOT NULL"))
        logging.getLogger(__name__).info("Migrated: added standards.examinable column")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_runtime()
    Base.metadata.create_all(bind=engine)
    _apply_lightweight_column_migrations(engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests. Please try again shortly."})
origins = [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Key"],
)
@app.get("/health")
def health():
    return {"status": "ok", "service": "dipifr-mastery-lab-api"}


@app.get("/")
def root():
    # A friendly response instead of a bare 404 when someone opens the
    # backend's base URL directly (e.g. while checking a deployment).
    return {
        "service": settings.app_name,
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
    }
app.include_router(auth_router)
app.include_router(learning_router)
app.include_router(exams_router)
app.include_router(tutor_router)
app.include_router(content_router)
app.include_router(admin_router)
