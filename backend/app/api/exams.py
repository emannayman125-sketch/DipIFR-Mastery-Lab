from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..core.ai_client import grade_answer_with_ai
from ..core.grading import keyword_grade
from ..db import get_db
from ..dependencies import current_user
from ..models import User, MockExam, MockExamQuestion, Question, ExamAttempt, ExamAnswer, TopicProgress, Standard, QuestionStandardLink, QuestionCriterion
from ..schemas.exam import (
    ExamSummary,
    ExamDetail,
    QuestionOut,
    StartAttemptResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    FinishAttemptResponse,
    ExamAnalysisResponse,
    QuestionAnalysis,
    StandardAnalysis,
    MarkingPointOut,
)

router = APIRouter(prefix="/exams", tags=["exams"])


def _exam_questions(db: Session, exam_id: int) -> list[Question]:
    links = db.scalars(
        select(MockExamQuestion)
        .where(MockExamQuestion.exam_id == exam_id)
        .order_by(MockExamQuestion.order_index)
    ).all()
    questions_by_id = {q.id: q for q in db.scalars(select(Question)).all()}
    return [questions_by_id[link.question_id] for link in links if link.question_id in questions_by_id]


def _is_expired(attempt: ExamAttempt) -> bool:
    expires = attempt.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= expires


def _linked_standard_codes(db: Session, question: Question) -> list[str]:
    """Same logic as learning.py's helper: every real standard a question
    touches via QuestionStandardLink, falling back to its own topic_code.
    Kept in sync here so mock-exam mastery updates use the same real
    standards as adaptive practice, instead of a possibly-fake topic_code
    label for cross-standard/past-exam questions."""
    links = db.scalars(select(QuestionStandardLink).where(QuestionStandardLink.question_id == question.id)).all()
    if not links:
        return [question.topic_code]
    standard_ids = [link.standard_id for link in links]
    codes = [s.code for s in db.scalars(select(Standard).where(Standard.id.in_(standard_ids))).all()]
    return codes or [question.topic_code]


@router.get("", response_model=list[ExamSummary])
def list_exams(db: Session = Depends(get_db)):
    exams = db.scalars(select(MockExam)).all()
    result = []
    for exam in exams:
        count = db.scalar(
            select(func.count(MockExamQuestion.id))
            .where(MockExamQuestion.exam_id == exam.id)
        ) or 0
        result.append(
            ExamSummary(
                id=exam.id,
                title=exam.title,
                description=exam.description,
                duration_minutes=exam.duration_minutes,
                question_count=count,
                exam_type=exam.exam_type,
            )
        )
    return result


@router.post("/{exam_id}/start", response_model=StartAttemptResponse)
def start_attempt(exam_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    exam = db.scalar(select(MockExam).where(MockExam.id == exam_id))
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    questions = _exam_questions(db, exam_id)
    if not questions:
        raise HTTPException(status_code=409, detail="This exam has no questions configured yet.")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=exam.duration_minutes)
    attempt = ExamAttempt(user_id=user.id, exam_id=exam_id, expires_at=expires_at)
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    detail = ExamDetail(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        duration_minutes=exam.duration_minutes,
        question_count=len(questions),
        questions=[
            QuestionOut(
                id=q.id, topic_code=q.topic_code, related_standards=_linked_standard_codes(db, q),
                prompt=q.prompt, marks=q.marks, source_round=getattr(q, "source_round", ""),
            )
            for q in questions
        ],
    )
    return StartAttemptResponse(attempt_id=attempt.id, exam=detail, expires_at=expires_at.isoformat())


@router.post("/attempts/{attempt_id}/draft")
def save_draft_answer(
    attempt_id: int,
    data: SubmitAnswerRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Lightweight autosave: persists the answer text/response mode without
    triggering AI/keyword grading. Called frequently (debounced) while the
    student is still typing, so it must stay cheap — grading only happens
    on the real submit_answer call (advancing questions or finishing)."""
    attempt = db.scalar(select(ExamAttempt).where(ExamAttempt.id == attempt_id, ExamAttempt.user_id == user.id))
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.submitted_at is not None:
        raise HTTPException(status_code=409, detail="This attempt has already been submitted")
    if _is_expired(attempt):
        raise HTTPException(status_code=409, detail="This exam attempt has expired")

    question = db.scalar(
        select(Question)
        .join(MockExamQuestion, MockExamQuestion.question_id == Question.id)
        .where(MockExamQuestion.exam_id == attempt.exam_id, Question.id == data.question_id)
    )
    if not question:
        raise HTTPException(status_code=400, detail="Question does not belong to this exam")

    existing = db.scalar(
        select(ExamAnswer).where(ExamAnswer.attempt_id == attempt_id, ExamAnswer.question_id == data.question_id)
    )
    if existing:
        existing.answer_text = data.answer_text
        existing.response_mode = data.response_mode
    else:
        db.add(
            ExamAnswer(
                attempt_id=attempt_id, question_id=data.question_id,
                answer_text=data.answer_text, response_mode=data.response_mode,
                score_percent=0, feedback="",
            )
        )
    db.commit()
    return {"saved": True}


@router.post("/attempts/{attempt_id}/answer", response_model=SubmitAnswerResponse)
async def submit_answer(
    attempt_id: int,
    data: SubmitAnswerRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    attempt = db.scalar(select(ExamAttempt).where(ExamAttempt.id == attempt_id, ExamAttempt.user_id == user.id))
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.submitted_at is not None:
        raise HTTPException(status_code=409, detail="This attempt has already been submitted")
    if _is_expired(attempt):
        attempt.submitted_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=409, detail="This exam attempt has expired")

    # Critical authorization check: a user may only answer questions that belong
    # to the exam attached to this attempt.
    question = db.scalar(
        select(Question)
        .join(MockExamQuestion, MockExamQuestion.question_id == Question.id)
        .where(MockExamQuestion.exam_id == attempt.exam_id, Question.id == data.question_id)
    )
    if not question:
        raise HTTPException(status_code=400, detail="Question does not belong to this exam")

    ai_result = await grade_answer_with_ai(question.prompt, question.model_answer, data.answer_text)
    if ai_result:
        score_percent, feedback = ai_result
        graded_by_ai = True
    else:
        score_percent, feedback = keyword_grade(data.answer_text, question.rubric_keywords)
        graded_by_ai = False

    existing = db.scalar(
        select(ExamAnswer).where(
            ExamAnswer.attempt_id == attempt_id,
            ExamAnswer.question_id == data.question_id,
        )
    )
    if existing:
        existing.answer_text = data.answer_text
        existing.response_mode = data.response_mode
        existing.score_percent = score_percent
        existing.feedback = feedback
        existing.is_graded = True
    else:
        db.add(
            ExamAnswer(
                attempt_id=attempt_id,
                question_id=data.question_id,
                answer_text=data.answer_text,
                response_mode=data.response_mode,
                score_percent=score_percent,
                feedback=feedback,
                is_graded=True,
            )
        )
    db.commit()

    return SubmitAnswerResponse(
        question_id=data.question_id,
        score_percent=score_percent,
        feedback=feedback,
        graded_by_ai=graded_by_ai,
    )


@router.post("/attempts/{attempt_id}/finish", response_model=FinishAttemptResponse)
async def finish_attempt(attempt_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    attempt = db.scalar(select(ExamAttempt).where(ExamAttempt.id == attempt_id, ExamAttempt.user_id == user.id))
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.submitted_at is not None:
        raise HTTPException(status_code=409, detail="This attempt has already been submitted")

    total_questions = _exam_questions(db, attempt.exam_id)
    allowed_ids = {q.id for q in total_questions}
    questions_by_id = {q.id: q for q in total_questions}
    answers = [
        a for a in db.scalars(select(ExamAnswer).where(ExamAnswer.attempt_id == attempt_id)).all()
        if a.question_id in allowed_ids
    ]

    # Grade any answer that was only ever autosaved as a draft (e.g. the
    # student clicked "Finish exam" straight from a question they hadn't
    # explicitly advanced past yet) so nothing is scored as 0 purely because
    # of *when* they stopped typing.
    for answer in answers:
        if answer.is_graded or not answer.answer_text.strip():
            continue
        question = questions_by_id[answer.question_id]
        ai_result = await grade_answer_with_ai(question.prompt, question.model_answer, answer.answer_text)
        if ai_result:
            answer.score_percent, answer.feedback = ai_result
        else:
            answer.score_percent, answer.feedback = keyword_grade(answer.answer_text, question.rubric_keywords)
        answer.is_graded = True
    db.flush()

    # A submitted answer is scored against the number of marks represented by
    # the fixed exam, not against the number of answers the client happened to send.
    total_marks = sum(q.marks for q in total_questions)
    earned_marks = sum(q.marks * a.score_percent / 100 for q in total_questions for a in answers if a.question_id == q.id)
    overall = round((earned_marks / total_marks) * 100) if total_marks else 0

    # Feed completed mock-exam evidence into the same mastery engine used by
    # adaptive practice. Mock selection itself remains fixed; only the
    # resulting performance updates the learner profile.
    learning_rate = 0.30
    for question in total_questions:
        answer = next((a for a in answers if a.question_id == question.id), None)
        if not answer:
            continue
        for topic_code in _linked_standard_codes(db, question):
            progress = db.scalar(
                select(TopicProgress).where(
                    TopicProgress.user_id == user.id, TopicProgress.topic_code == topic_code
                )
            )
            if not progress:
                progress = TopicProgress(user_id=user.id, topic_code=topic_code, mastery=0)
                db.add(progress)
                db.flush()
            progress.mastery = round(progress.mastery * (1 - learning_rate) + answer.score_percent * learning_rate)

    attempt.submitted_at = datetime.now(timezone.utc)
    attempt.score_percent = overall
    db.commit()

    return FinishAttemptResponse(
        attempt_id=attempt.id,
        score_percent=overall,
        answered_questions=len(answers),
        total_questions=len(total_questions),
    )


@router.get("/attempts/{attempt_id}/analysis", response_model=ExamAnalysisResponse)
def exam_analysis(attempt_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Full post-exam breakdown: marks earned per question (with the
    question's marking-point rubric for review) and marks aggregated per
    standard, so a student can see not just their overall %, but exactly
    which standards cost them marks."""
    attempt = db.scalar(select(ExamAttempt).where(ExamAttempt.id == attempt_id, ExamAttempt.user_id == user.id))
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.submitted_at is None:
        raise HTTPException(status_code=409, detail="This attempt has not been finished yet")

    questions = _exam_questions(db, attempt.exam_id)
    answers_by_qid = {
        a.question_id: a
        for a in db.scalars(select(ExamAnswer).where(ExamAnswer.attempt_id == attempt_id)).all()
    }

    by_question: list[QuestionAnalysis] = []
    standard_totals: dict[str, dict[str, float]] = {}

    for q in questions:
        answer = answers_by_qid.get(q.id)
        score_percent = answer.score_percent if answer else 0
        marks_earned = round(q.marks * score_percent / 100, 2)
        related = _linked_standard_codes(db, q)
        criteria = db.scalars(select(QuestionCriterion).where(QuestionCriterion.question_id == q.id)).all()

        by_question.append(
            QuestionAnalysis(
                question_id=q.id, topic_code=q.topic_code, related_standards=related,
                source_round=q.source_round, marks_available=q.marks, marks_earned=marks_earned,
                score_percent=score_percent, feedback=answer.feedback if answer else "Not answered.",
                marking_points=[
                    MarkingPointOut(criterion=c.criterion, marks=c.marks, expected_points=c.expected_points)
                    for c in criteria
                ],
            )
        )

        # Split this question's marks evenly across every standard it
        # touches, so a cross-standard question contributes to each real
        # standard's analysis rather than only its primary tag.
        share_available = q.marks / len(related) if related else q.marks
        share_earned = marks_earned / len(related) if related else marks_earned
        for code in related or [q.topic_code]:
            bucket = standard_totals.setdefault(code, {"available": 0.0, "earned": 0.0})
            bucket["available"] += share_available
            bucket["earned"] += share_earned

    by_standard = [
        StandardAnalysis(
            code=code,
            marks_available=round(v["available"]),
            marks_earned=round(v["earned"], 2),
            score_percent=round((v["earned"] / v["available"]) * 100) if v["available"] else 0,
        )
        for code, v in sorted(standard_totals.items())
    ]

    total_marks = sum(q.marks_available for q in by_question)
    earned_marks = sum(q.marks_earned for q in by_question)

    return ExamAnalysisResponse(
        attempt_id=attempt.id,
        score_percent=attempt.score_percent or 0,
        total_marks=total_marks,
        earned_marks=round(earned_marks, 2),
        by_question=by_question,
        by_standard=by_standard,
    )
