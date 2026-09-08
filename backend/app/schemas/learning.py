from pydantic import BaseModel, Field


class ProgressResponse(BaseModel):
    user_id: int
    overall: int
    topics: dict[str, int]


class WeakStandard(BaseModel):
    code: str
    title: str
    mastery: int


class MockScoreHistoryPoint(BaseModel):
    exam_id: int
    title: str
    score_percent: int
    submitted_at: str


class MyLevelResponse(BaseModel):
    overall_mastery: int
    exam_readiness_percent: int  # overall_mastery expressed against the 50% real-exam pass mark
    is_exam_ready: bool
    weakest_standards: list[WeakStandard]
    strongest_standards: list[WeakStandard]
    mock_score_history: list[MockScoreHistoryPoint]
    mock_average_percent: int | None
    standards_practiced: int
    standards_total: int


class NextQuestionResponse(BaseModel):
    question_id: int
    topic_code: str
    related_standards: list[str] = Field(default_factory=list)
    prompt: str
    marks: int
    source: str = "original"
    source_round: str = ""
    source_reference: str = ""
    question_number: int | None = None


class PracticeSubmitRequest(BaseModel):
    question_id: int
    answer_text: str = Field(min_length=1, max_length=4000)
    response_mode: str = Field(default="word_processor", pattern="^(word_processor|spreadsheet)$")


class PracticeSubmitResponse(BaseModel):
    question_id: int
    topic_code: str
    related_standards: list[str] = Field(default_factory=list)
    score_percent: int
    feedback: str
    graded_by_ai: bool
    new_mastery: int
    overall: int
