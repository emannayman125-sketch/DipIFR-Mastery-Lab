from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base


class TopicProgress(Base):
    """Tracks a single user's mastery percentage for a single IFRS/IAS topic code."""
    __tablename__ = "topic_progress"
    __table_args__ = (UniqueConstraint("user_id", "topic_code", name="uq_user_topic"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_code: Mapped[str] = mapped_column(String(120))
    mastery: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


class PracticeAttempt(Base):
    """Records each practice-question attempt so mastery changes are auditable, not just overwritten."""
    __tablename__ = "practice_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_code: Mapped[str] = mapped_column(String(120))
    answer_text: Mapped[str] = mapped_column(String(4000))
    response_mode: Mapped[str] = mapped_column(String(20), default="word_processor")
    mastery_delta: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
