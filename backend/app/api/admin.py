from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from fastapi import Depends

from ..core.config import settings
from ..db import get_db
from ..models import User, TopicProgress, PracticeAttempt

router = APIRouter(prefix="/admin", tags=["admin"])


def _check_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    """Simple shared-secret guard — not tied to a specific user account, so
    no schema migration is needed. Set ADMIN_KEY in the server environment
    and pass the same value as the X-Admin-Key header from the frontend."""
    if not settings.admin_key:
        raise HTTPException(status_code=503, detail="Admin access is not configured on this server (no ADMIN_KEY set).")
    if not x_admin_key or x_admin_key != settings.admin_key:
        raise HTTPException(status_code=401, detail="Invalid or missing admin key")


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _: None = Depends(_check_admin_key),
):
    """Every registered student, most recently registered first, with a
    quick view of their verification status and how much practice they've
    logged so far."""
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()

    # Attempt counts per user in one query rather than N+1.
    attempt_counts = dict(
        db.execute(
            select(PracticeAttempt.user_id, func.count(PracticeAttempt.id)).group_by(PracticeAttempt.user_id)
        ).all()
    )
    topic_counts = dict(
        db.execute(
            select(TopicProgress.user_id, func.count(TopicProgress.id)).group_by(TopicProgress.user_id)
        ).all()
    )

    return [
        {
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "is_verified": u.is_verified,
            "created_at": u.created_at.isoformat() if isinstance(u.created_at, datetime) else u.created_at,
            "practice_attempts": attempt_counts.get(u.id, 0),
            "standards_started": topic_counts.get(u.id, 0),
        }
        for u in users
    ]
