from pydantic import BaseModel, Field


class TutorMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class TutorAskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[TutorMessage] = Field(default_factory=list)
    question_context: str | None = Field(default=None, max_length=4000)


class TutorAskResponse(BaseModel):
    reply: str
    ai_generated: bool
