import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import current_user
from ..models import User, TopicProgress, PracticeAttempt, Question, Standard, QuestionStandardLink, MockExam, ExamAttempt
from ..schemas.learning import (
    ProgressResponse,
    NextQuestionResponse,
    PracticeSubmitRequest,
    PracticeSubmitResponse,
    MyLevelResponse,
    WeakStandard,
    MockScoreHistoryPoint,
)
from ..core.grading import keyword_grade
from ..core.ai_client import grade_answer_with_ai

router = APIRouter(prefix="/learning", tags=["learning"])

MAX_MASTERY = 100
# A student's mastery moves toward their score on this attempt rather than
# just ticking up a fixed amount — a strong answer should move the needle
# more than a weak one.
MASTERY_LEARNING_RATE = 0.3


def _topics_for(db: Session, user_id: int) -> dict[str, int]:
    rows = db.scalars(select(TopicProgress).where(TopicProgress.user_id == user_id)).all()
    return {row.topic_code: row.mastery for row in rows}


def _overall(topics: dict[str, int]) -> int:
    if not topics:
        return 0
    return round(sum(topics.values()) / len(topics))


def _linked_standard_codes(db: Session, question: Question) -> list[str]:
    """Every real standard a question actually touches, via the
    QuestionStandardLink table. Falls back to the question's own
    topic_code when no links exist (e.g. legacy/manually added rows),
    so mastery tracking never silently drops a question.

    This matters most for cross-standard questions, whose topic_code is a
    human-readable label (e.g. "PPE + Borrowing Costs") rather than a real
    standard code — without this, practising them would never move the
    mastery shown on the actual IAS 16 / IAS 23 standard cards.
    """
    links = db.scalars(select(QuestionStandardLink).where(QuestionStandardLink.question_id == question.id)).all()
    if not links:
        return [question.topic_code]
    standard_ids = [link.standard_id for link in links]
    codes = [s.code for s in db.scalars(select(Standard).where(Standard.id.in_(standard_ids))).all()]
    return codes or [question.topic_code]


@router.get("/progress", response_model=ProgressResponse)
def progress(user: User = Depends(current_user), db: Session = Depends(get_db)):
    topics = _topics_for(db, user.id)
    return ProgressResponse(user_id=user.id, overall=_overall(topics), topics=topics)


# The real ACCA DipIFR exam pass mark is 50%. "Exam readiness" is expressed
# as a percentage of that bar, not of the full 0-100 mastery scale, so 100%
# readiness means "at the pass mark", not "perfect on every standard" —
# reaching 50% mastery genuinely is the realistic target, not 100%.
REAL_EXAM_PASS_MARK = 50


@router.get("/my-level", response_model=MyLevelResponse)
def my_level(user: User = Depends(current_user), db: Session = Depends(get_db)):
    topics = _topics_for(db, user.id)
    overall = _overall(topics)

    all_standards = {s.code: s.title for s in db.scalars(select(Standard)).all()}
    ranked = sorted(
        ({"code": code, "title": all_standards.get(code, code), "mastery": mastery} for code, mastery in topics.items()),
        key=lambda row: row["mastery"],
    )
    weakest = [WeakStandard(**row) for row in ranked[:5]]
    strongest = [WeakStandard(**row) for row in ranked[-3:][::-1]] if ranked else []

    attempts = db.scalars(
        select(ExamAttempt)
        .where(ExamAttempt.user_id == user.id, ExamAttempt.submitted_at.isnot(None))
        .order_by(ExamAttempt.submitted_at)
    ).all()
    exam_titles = {e.id: e.title for e in db.scalars(select(MockExam)).all()}
    history = [
        MockScoreHistoryPoint(
            exam_id=a.exam_id,
            title=exam_titles.get(a.exam_id, "Mock exam"),
            score_percent=a.score_percent or 0,
            submitted_at=a.submitted_at.isoformat(),
        )
        for a in attempts
    ]
    mock_average = round(sum(h.score_percent for h in history) / len(history)) if history else None
    # "Mock exams" here counts BOTH the 7 original AI-graded "Mastery Mock"
    # exams AND the 21 real ACCA "Past Round — {sitting}" exams (reference
    # question text with keyword grading — see PRODUCTION_CHECKLIST.md for
    # why their text isn't reproduced in full). Counting only one type would
    # understate how much real, attemptable exam content is actually here.
    total_mocks = db.scalar(select(func.count()).select_from(MockExam).where(
        or_(MockExam.title.like("Mastery Mock%"), MockExam.title.like("Past Round%"))
    )) or 0
    completed_mock_ids = {
        a.exam_id for a in attempts
        if exam_titles.get(a.exam_id, "").startswith(("Mastery Mock", "Past Round"))
    }

    return MyLevelResponse(
        overall_mastery=overall,
        exam_readiness_percent=min(100, round(overall / REAL_EXAM_PASS_MARK * 100)) if overall else 0,
        is_exam_ready=overall >= REAL_EXAM_PASS_MARK,
        weakest_standards=weakest,
        strongest_standards=strongest,
        mock_score_history=history,
        mock_average_percent=mock_average,
        standards_practiced=len(topics),
        standards_total=len(all_standards),
        mocks_completed=len(completed_mock_ids),
        mocks_total=total_mocks,
    )


@router.get("/practice/next", response_model=NextQuestionResponse)
def next_question(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Picks a question from the standard the student is currently weakest in
    (adaptive selection — practice only, never used for mock exams)."""
    topics = _topics_for(db, user.id)
    all_standard_codes = [row[0] for row in db.execute(select(Standard.code))]
    if not all_standard_codes:
        raise HTTPException(status_code=404, detail="No standards are configured yet.")

    # Weakest tracked standard, or a random one if the student has no history yet.
    if topics:
        ranked = sorted(all_standard_codes, key=lambda code: topics.get(code, 0))
        target_code = ranked[0]
    else:
        target_code = random.choice(all_standard_codes)

    target_standard = db.scalar(select(Standard).where(Standard.code == target_code))
    linked_question_ids = db.scalars(
        select(QuestionStandardLink.question_id).where(QuestionStandardLink.standard_id == target_standard.id)
    )
    # Include both questions tagged directly with this code AND questions
    # linked to this standard via QuestionStandardLink (covers cross-standard
    # and past-exam questions whose topic_code isn't the plain standard code).
    candidates = db.scalars(
        select(Question).where(or_(Question.topic_code == target_code, Question.id.in_(linked_question_ids)))
    ).all()
    if not candidates:
        raise HTTPException(status_code=404, detail=f"No questions available yet for {target_code}.")

    question = random.choice(candidates)
    related = _linked_standard_codes(db, question)
    return NextQuestionResponse(
        question_id=question.id,
        topic_code=question.topic_code,
        related_standards=related,
        prompt=question.prompt,
        marks=question.marks,
        source=question.source,
        source_round=question.source_round,
        source_reference=question.source_reference,
        question_number=question.question_number,
    )


@router.post("/practice/submit", response_model=PracticeSubmitResponse)
async def submit_practice(
    data: PracticeSubmitRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    question = db.scalar(select(Question).where(Question.id == data.question_id))
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Past-exam-sourced questions no longer store ACCA's real question text or
    # suggested answer (removed for copyright reasons — see seed_data.py), so
    # there's nothing meaningful left to hand the AI as "the model answer" for
    # those. Grade them with our own keyword rubric instead of risking a
    # nonsense AI comparison against a placeholder.
    if question.source == "past_exam":
        score_percent, feedback = keyword_grade(data.answer_text, question.rubric_keywords)
        graded_by_ai = False
    else:
        ai_result = await grade_answer_with_ai(question.prompt, question.model_answer, data.answer_text)
        if ai_result:
            score_percent, feedback = ai_result
            graded_by_ai = True
        else:
            score_percent, feedback = keyword_grade(data.answer_text, question.rubric_keywords)
            graded_by_ai = False

    related = _linked_standard_codes(db, question)

    # A cross-standard (or past-exam question linked to several standards)
    # moves mastery for every standard it genuinely touches, not just a
    # single fake "topic" label.
    for topic_code in related:
        row = db.scalar(
            select(TopicProgress).where(TopicProgress.user_id == user.id, TopicProgress.topic_code == topic_code)
        )
        if not row:
            row = TopicProgress(user_id=user.id, topic_code=topic_code, mastery=0)
            db.add(row)
        new_mastery = round(row.mastery + (score_percent - row.mastery) * MASTERY_LEARNING_RATE)
        delta = new_mastery - row.mastery
        row.mastery = max(0, min(MAX_MASTERY, new_mastery))
        db.add(
            PracticeAttempt(
                user_id=user.id, topic_code=topic_code, answer_text=data.answer_text,
                response_mode=data.response_mode, mastery_delta=delta
            )
        )
    db.commit()

    topics = _topics_for(db, user.id)
    primary_topic = related[0] if related else question.topic_code
    return PracticeSubmitResponse(
        question_id=question.id,
        topic_code=question.topic_code,
        related_standards=related,
        score_percent=score_percent,
        feedback=feedback,
        graded_by_ai=graded_by_ai,
        new_mastery=topics.get(primary_topic, score_percent),
        overall=_overall(topics),
    )
