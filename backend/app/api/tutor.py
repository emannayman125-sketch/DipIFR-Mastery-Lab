from fastapi import APIRouter, Depends, Request

from ..core.config import settings
from ..core.limiter import limiter
from ..dependencies import current_user
from ..models import User
from ..schemas.tutor import TutorAskRequest, TutorAskResponse
from ..core.ai_client import ask_tutor

router = APIRouter(prefix="/tutor", tags=["tutor"])


@router.post("/ask", response_model=TutorAskResponse)
@limiter.limit(settings.rate_limit_tutor)
async def ask(request: Request, data: TutorAskRequest, user: User = Depends(current_user)):
    history = [{"role": m.role, "content": m.content} for m in data.history]
    reply, ai_generated = await ask_tutor(data.message, history=history, question_context=data.question_context)
    return TutorAskResponse(reply=reply, ai_generated=ai_generated)
