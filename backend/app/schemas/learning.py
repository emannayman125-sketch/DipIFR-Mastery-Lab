from pydantic import BaseModel, Field


class ProgressResponse(BaseModel):
    user_id: int
    overall: int
    topics: dict[str, int]


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
