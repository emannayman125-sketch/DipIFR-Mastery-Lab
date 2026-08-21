from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from .core.config import settings
from .core.limiter import limiter
from .db import Base, engine, SessionLocal
from .api.auth import router as auth_router
from .api.learning import router as learning_router
from .api.exams import router as exams_router
from .api.tutor import router as tutor_router
from .api.content import router as content_router
from .models import User, TopicProgress, PracticeAttempt, RefreshToken, Question, MockExam, MockExamQuestion, ExamAttempt, ExamAnswer, Standard, Topic, LearningResource, PastExamSession, QuestionStandardLink, QuestionCriterion
from .seed_data import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_runtime()
    Base.metadata.create_all(bind=engine)
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
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "dipifr-mastery-lab-api"}


app.include_router(auth_router)
app.include_router(learning_router)
app.include_router(exams_router)
app.include_router(tutor_router)
app.include_router(content_router)
