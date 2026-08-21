import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db import Base, get_db
from app.seed_data import seed_if_empty


@pytest.fixture()
def client():
    # Fresh in-memory DB per test so tests never leak state into each other
    # or into a developer's local dipifr.db file.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    seed_db = TestingSessionLocal()
    seed_if_empty(seed_db)
    seed_db.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # slowapi's in-memory limiter storage is process-global and keyed by
    # client IP, which is identical ("testclient") across every TestClient
    # instance — reset it so rate limits from one test don't bleed into the
    # next.
    from app.core.limiter import limiter
    limiter.reset()

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
