from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base


class Standard(Base):
    __tablename__ = 'standards'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default='')
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Topic(Base):
    __tablename__ = 'topics'
    id: Mapped[int] = mapped_column(primary_key=True)
    standard_id: Mapped[int] = mapped_column(ForeignKey('standards.id', ondelete='CASCADE'), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default='')
    __table_args__ = (UniqueConstraint('standard_id', 'code', name='uq_standard_topic'),)


class LearningResource(Base):
    __tablename__ = 'learning_resources'
    id: Mapped[int] = mapped_column(primary_key=True)
    standard_id: Mapped[int | None] = mapped_column(ForeignKey('standards.id', ondelete='SET NULL'), nullable=True, index=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey('topics.id', ondelete='SET NULL'), nullable=True, index=True)
    resource_type: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(250))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(120), default='original')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PastExamSession(Base):
    __tablename__ = 'past_exam_sessions'
    id: Mapped[int] = mapped_column(primary_key=True)
    session_name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    exam_date: Mapped[str] = mapped_column(String(40))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=195)
    total_marks: Mapped[int] = mapped_column(Integer, default=100)
    source_type: Mapped[str] = mapped_column(String(40), default='reference_only')
    source_reference: Mapped[str] = mapped_column(String(300), default='')
    question_count: Mapped[int] = mapped_column(Integer, default=4)
    available_for_simulation: Mapped[bool] = mapped_column(Boolean, default=False)


class QuestionStandardLink(Base):
    __tablename__ = 'question_standard_links'
    question_id: Mapped[int] = mapped_column(ForeignKey('questions.id', ondelete='CASCADE'), primary_key=True)
    standard_id: Mapped[int] = mapped_column(ForeignKey('standards.id', ondelete='CASCADE'), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default='related')


class QuestionCriterion(Base):
    __tablename__ = 'question_criteria'
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('questions.id', ondelete='CASCADE'), index=True)
    criterion: Mapped[str] = mapped_column(String(200))
    marks: Mapped[int] = mapped_column(Integer)
    expected_points: Mapped[str] = mapped_column(Text)
