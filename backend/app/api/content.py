from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from pathlib import Path
import json
from ..db import get_db
from ..dependencies import current_user
from ..models import User, Standard, Topic, Question, QuestionStandardLink, PastExamSession, TopicProgress
from ..schemas.content import StandardOut, QuestionBankItem, PastExamOut, OfficialResourceOut

router = APIRouter(prefix='/content', tags=['content'])

_OFFICIAL_RESOURCES_PATH = Path(__file__).resolve().parent.parent / "data" / "official_resources.json"


@router.get('/official-resources', response_model=list[OfficialResourceOut])
def official_resources():
    """Curated links to ACCA's own official DipIFR pages (past papers, CBE
    demo, mock exams, syllabus). The platform never reproduces ACCA's
    copyrighted exam content itself — this section exists specifically so
    students can go straight to the authentic source when they want it."""
    data = json.loads(_OFFICIAL_RESOURCES_PATH.read_text(encoding="utf-8"))
    return [OfficialResourceOut(**item) for item in data]

@router.get('/standards', response_model=list[StandardOut])
def standards(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Standard).where(Standard.active.is_(True)).order_by(Standard.code)).all()
    result = []
    for s in rows:
        count = db.scalar(select(func.count(QuestionStandardLink.question_id)).where(QuestionStandardLink.standard_id == s.id)) or 0
        p = db.scalar(select(TopicProgress).where(TopicProgress.user_id == user.id, TopicProgress.topic_code == s.code))
        result.append(StandardOut(id=s.id, code=s.code, title=s.title, description=s.description, question_count=count, mastery=p.mastery if p else 0))
    return result

@router.get('/questions', response_model=list[QuestionBankItem])
def question_bank(
    standard: str | None = None,
    difficulty: str | None = None,
    integrated: bool | None = None,
    source: str | None = Query(default=None, description="Filter by source, e.g. 'past_exam', 'original', 'original_cross_standard'"),
    question_type: str | None = Query(default=None, description="Filter by question_type, e.g. 'flagship_core', 'cross_standard'"),
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=300),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Question, Standard).join(QuestionStandardLink, QuestionStandardLink.question_id == Question.id).join(Standard, Standard.id == QuestionStandardLink.standard_id).where(QuestionStandardLink.role == 'primary')
    if standard:
        stmt = stmt.where(Standard.code == standard)
    if difficulty:
        stmt = stmt.where(Question.difficulty == difficulty)
    if source:
        stmt = stmt.where(Question.source == source)
    if question_type:
        stmt = stmt.where(Question.question_type == question_type)
    if integrated is not None:
        if integrated:
            stmt = stmt.where(Question.id.in_(select(QuestionStandardLink.question_id).group_by(QuestionStandardLink.question_id).having(func.count(QuestionStandardLink.standard_id) > 1)))
        else:
            stmt = stmt.where(Question.id.in_(select(QuestionStandardLink.question_id).group_by(QuestionStandardLink.question_id).having(func.count(QuestionStandardLink.standard_id) == 1)))
    if q:
        like = f'%{q}%'
        stmt = stmt.where(or_(Question.prompt.ilike(like), Question.topic_code.ilike(like)))
    # Explicit, deterministic ordering — without this, an unfiltered browse
    # at the default limit could silently omit an entire category (e.g. the
    # real past-exam questions, which are seeded last and therefore have the
    # highest IDs) purely because of how the DB happens to return unordered
    # rows once the bank grew past the default page size.
    rows = db.execute(stmt.order_by(Question.id).limit(limit)).all()
    result = []
    for question, primary in rows:
        links = db.scalars(select(QuestionStandardLink).where(QuestionStandardLink.question_id == question.id)).all()
        codes = [s.code for s in db.scalars(select(Standard).where(Standard.id.in_([x.standard_id for x in links]))).all()]
        result.append(QuestionBankItem(id=question.id, standard_code=primary.code, topic=question.topic_code, question_type=getattr(question, 'question_type', 'written'), difficulty=getattr(question, 'difficulty', 'medium'), marks=question.marks, source=getattr(question, 'source', 'original'), prompt=question.prompt, integrated=len(codes)>1, related_standards=codes, source_round=getattr(question, "source_round", ""), question_number=getattr(question, "question_number", None), source_reference=getattr(question, "source_reference", "")))
    return result

@router.get('/past-exams', response_model=list[PastExamOut])
def past_exams(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(PastExamSession).order_by(PastExamSession.exam_date.desc())).all()
    return [PastExamOut(id=x.id, session_name=x.session_name, exam_date=x.exam_date, duration_minutes=x.duration_minutes, total_marks=x.total_marks, question_count=x.question_count, available_for_simulation=x.available_for_simulation, source_type=x.source_type) for x in rows]


@router.get('/past-exams/{session_id}/questions', response_model=list[QuestionBankItem])
def past_exam_questions(session_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Question).where(Question.past_exam_session_id == session_id).order_by(Question.question_number)).all()
    result=[]
    for question in rows:
        links=db.scalars(select(QuestionStandardLink).where(QuestionStandardLink.question_id==question.id)).all()
        codes=[s.code for s in db.scalars(select(Standard).where(Standard.id.in_([x.standard_id for x in links]))).all()] if links else []
        primary=codes[0] if codes else question.topic_code
        result.append(QuestionBankItem(id=question.id, standard_code=primary, topic=question.topic_code, question_type=question.question_type, difficulty=question.difficulty, marks=question.marks, source=question.source, prompt=question.prompt, integrated=len(codes)>1, related_standards=codes, source_round=question.source_round, question_number=question.question_number, source_reference=question.source_reference))
    return result
