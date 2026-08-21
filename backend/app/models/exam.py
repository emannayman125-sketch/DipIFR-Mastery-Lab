from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, UniqueConstraint, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base


class Question(Base):
    """A single exam-style question, with a model answer + rubric keywords
    used as a fallback when AI grading isn't configured."""
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_code: Mapped[str] = mapped_column(String(120), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    model_answer: Mapped[str] = mapped_column(Text)
    rubric_keywords: Mapped[str] = mapped_column(Text)  # comma-separated, used by the fallback grader
    marks: Mapped[int] = mapped_column(Integer, default=10)
    question_type: Mapped[str] = mapped_column(String(40), default='written', index=True)
    difficulty: Mapped[str] = mapped_column(String(20), default='medium', index=True)
    source: Mapped[str] = mapped_column(String(40), default='original', index=True)
    learning_objective: Mapped[str] = mapped_column(Text, default='')
    source_round: Mapped[str] = mapped_column(String(100), default='', index=True)
    source_reference: Mapped[str] = mapped_column(String(400), default='')
    question_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    past_exam_session_id: Mapped[int | None] = mapped_column(ForeignKey("past_exam_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    review_status: Mapped[str] = mapped_column(String(30), default='approved', index=True)


class MockExam(Base):
    """A fixed-format exam blueprint. Deliberately NOT personalised per user."""
    __tablename__ = "mock_exams"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=180)
    exam_type: Mapped[str] = mapped_column(String(30), default='original_mock', index=True)
    past_exam_session_id: Mapped[int | None] = mapped_column(ForeignKey("past_exam_sessions.id", ondelete="SET NULL"), nullable=True, index=True)


class MockExamQuestion(Base):
    """Ordered link between an exam and its fixed set of questions."""
    __tablename__ = "mock_exam_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("mock_exams.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class ExamAttempt(Base):
    """One user's attempt at one mock exam."""
    __tablename__ = "exam_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("mock_exams.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    score_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ExamAnswer(Base):
    """A single question's answer within an exam attempt."""
    __tablename__ = "exam_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("exam_attempts.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    answer_text: Mapped[str] = mapped_column(Text)
    response_mode: Mapped[str] = mapped_column(String(20), default="word_processor")
    is_graded: Mapped[bool] = mapped_column(Boolean, default=False)
    score_percent: Mapped[int] = mapped_column(Integer, default=0)
    feedback: Mapped[str] = mapped_column(Text, default="")
