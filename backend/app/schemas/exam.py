from pydantic import BaseModel, Field


class QuestionOut(BaseModel):
    id: int
    topic_code: str
    related_standards: list[str] = Field(default_factory=list)
    prompt: str
    marks: int
    source_round: str = ""


class ExamSummary(BaseModel):
    id: int
    title: str
    description: str
    duration_minutes: int
    question_count: int
    exam_type: str = "original_mock"


class ExamDetail(ExamSummary):
    questions: list[QuestionOut]


class StartAttemptResponse(BaseModel):
    attempt_id: int
    exam: ExamDetail
    expires_at: str


class SubmitAnswerRequest(BaseModel):
    question_id: int
    answer_text: str = Field(min_length=1, max_length=4000)
    response_mode: str = Field(default="word_processor", pattern="^(word_processor|spreadsheet)$")


class SubmitAnswerResponse(BaseModel):
    question_id: int
    score_percent: int
    feedback: str
    graded_by_ai: bool


class FinishAttemptResponse(BaseModel):
    attempt_id: int
    score_percent: int
    answered_questions: int
    total_questions: int


class MarkingPointOut(BaseModel):
    criterion: str
    marks: int
    expected_points: str


class QuestionAnalysis(BaseModel):
    question_id: int
    topic_code: str
    related_standards: list[str] = Field(default_factory=list)
    source_round: str = ""
    marks_available: int
    marks_earned: float
    score_percent: int
    feedback: str
    marking_points: list[MarkingPointOut] = Field(default_factory=list)


class StandardAnalysis(BaseModel):
    code: str
    marks_available: int
    marks_earned: float
    score_percent: int


class ExamAnalysisResponse(BaseModel):
    attempt_id: int
    score_percent: int
    total_marks: int
    earned_marks: float
    by_question: list[QuestionAnalysis]
    by_standard: list[StandardAnalysis]
