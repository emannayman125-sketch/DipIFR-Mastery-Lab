from pydantic import BaseModel

class StandardOut(BaseModel):
    id: int
    code: str
    title: str
    description: str
    question_count: int
    mastery: int = 0

class QuestionBankItem(BaseModel):
    id: int
    standard_code: str
    topic: str
    question_type: str
    difficulty: str
    marks: int
    source: str
    prompt: str
    integrated: bool
    related_standards: list[str]
    source_round: str = ""
    question_number: int | None = None
    source_reference: str = ""

class PastExamOut(BaseModel):
    id: int
    session_name: str
    exam_date: str
    duration_minutes: int
    total_marks: int
    question_count: int
    available_for_simulation: bool
    source_type: str

class OfficialResourceOut(BaseModel):
    title: str
    description: str
    url: str
