"""
Thin wrapper around an AI provider, used for:
  1) the AI tutor chat (now with real conversation memory + optional
     question context, e.g. "explain this question" from Practice/Exams), and
  2) AI-assisted grading of free-text practice answers.

Two providers are supported behind the same interface:
  - Anthropic (Claude) — used if ANTHROPIC_API_KEY is set.
  - Google Gemini — used if GEMINI_API_KEY is set and ANTHROPIC_API_KEY is
    not. Gemini has a genuinely free tier (no card required) via
    https://aistudio.google.com/apikey, so it's the easier option to turn
    the tutor on without a paid provider.
If ANTHROPIC_API_KEY is set, it takes priority over GEMINI_API_KEY.

Both keys live only in server environment variables and are never sent to
or read by the frontend. If neither key is configured, both call sites
fall back to clearly-labelled rule-based behaviour (keyword matching for
grading, a static explanatory message for the tutor) so the app stays
usable without secrets configured, instead of throwing 500s.
"""
import asyncio
import json
import logging

import httpx

from .config import settings

logger = logging.getLogger("dipifr.ai")

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
GEMINI_API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_HISTORY_MESSAGES = 12  # keep the tutor's context window bounded


class AIUnavailable(Exception):
    pass


def _active_provider() -> str | None:
    """Returns 'anthropic', 'gemini', or None if neither key is configured.
    Anthropic wins if both happen to be set."""
    if settings.anthropic_api_key:
        return "anthropic"
    if settings.gemini_api_key:
        return "gemini"
    return None


def is_configured() -> bool:
    return _active_provider() is not None


async def _call_anthropic(system: str, messages: list[dict], max_tokens: int, retries: int) -> str:
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": settings.anthropic_model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < retries:
                await asyncio.sleep(0.5)
                continue
            logger.warning("Anthropic API timed out after %d attempt(s)", attempt + 1)
            raise AIUnavailable("AI provider timed out") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < retries:
                await asyncio.sleep(0.5)
                continue
            logger.warning("Anthropic API network error: %s", exc)
            raise AIUnavailable("AI provider network error") from exc

        # 529/overloaded and 500-range errors are worth one retry; 4xx (bad
        # request, auth, etc.) never will succeed on retry.
        if response.status_code >= 500 and attempt < retries:
            await asyncio.sleep(0.5)
            continue

        if response.status_code != 200:
            logger.warning("Anthropic API error %s: %s", response.status_code, response.text[:500])
            raise AIUnavailable(f"AI provider returned status {response.status_code}")

        data = response.json()
        text_blocks = [block["text"] for block in data.get("content", []) if block.get("type") == "text"]
        return "\n".join(text_blocks).strip()

    raise AIUnavailable(str(last_error) if last_error else "AI provider call failed")


async def _call_gemini(system: str, messages: list[dict], max_tokens: int, retries: int) -> str:
    url = GEMINI_API_URL_TEMPLATE.format(model=settings.gemini_model)
    headers = {"content-type": "application/json"}
    params = {"key": settings.gemini_api_key}

    # Gemini has no separate "system" role in this endpoint's simplest form;
    # send it as systemInstruction and map our role names to Gemini's
    # ("assistant" -> "model").
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": max_tokens},
    }

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, headers=headers, params=params, json=payload)
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < retries:
                await asyncio.sleep(0.5)
                continue
            logger.warning("Gemini API timed out after %d attempt(s)", attempt + 1)
            raise AIUnavailable("AI provider timed out") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < retries:
                await asyncio.sleep(0.5)
                continue
            logger.warning("Gemini API network error: %s", exc)
            raise AIUnavailable("AI provider network error") from exc

        if response.status_code >= 500 and attempt < retries:
            await asyncio.sleep(0.5)
            continue
        # 429 (rate limit on the free tier) is also worth one retry.
        if response.status_code == 429 and attempt < retries:
            await asyncio.sleep(1.0)
            continue

        if response.status_code != 200:
            logger.warning("Gemini API error %s: %s", response.status_code, response.text[:500])
            raise AIUnavailable(f"AI provider returned status {response.status_code}")

        data = response.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "\n".join(p.get("text", "") for p in parts).strip()
        except (KeyError, IndexError) as exc:
            logger.warning("Gemini API returned an unexpected response shape: %s", data)
            raise AIUnavailable("AI provider returned an unexpected response") from exc

    raise AIUnavailable(str(last_error) if last_error else "AI provider call failed")


async def _call_ai(system: str, messages: list[dict], max_tokens: int = 600, retries: int = 1) -> str:
    provider = _active_provider()
    if provider == "anthropic":
        return await _call_anthropic(system, messages, max_tokens, retries)
    if provider == "gemini":
        return await _call_gemini(system, messages, max_tokens, retries)
    raise AIUnavailable("No AI provider is configured on the server")


TUTOR_SYSTEM_PROMPT = (
    "You are a patient, precise DipIFR (ACCA Diploma in IFRS) tutor. "
    "Explain concepts clearly with correct IFRS/IAS terminology, use short "
    "worked examples where useful, and point out common exam pitfalls. "
    "Keep answers focused and exam-relevant. Never fabricate a standard or "
    "paragraph reference you are not confident about — say so instead. "
    "If the student's message includes '[Question context]', treat that as "
    "the exam question they are currently looking at and ground your "
    "explanation in it specifically rather than answering generically."
)


async def ask_tutor(
    message: str,
    history: list[dict] | None = None,
    question_context: str | None = None,
) -> tuple[str, bool]:
    """Returns (answer_text, was_ai_generated).

    `history` is a list of {"role": "user"|"assistant", "content": str}
    from earlier turns in the same conversation, so the tutor can handle
    natural follow-ups ("what about IAS 23 in the same scenario?") instead
    of treating every message as an isolated question.

    `question_context`, if provided (e.g. from a "Explain this question"
    button on a Practice/Exam question), is prepended so the tutor answers
    about that specific question rather than in the abstract.
    """
    if not is_configured():
        return (
            "The AI tutor isn't connected yet on this server (no ANTHROPIC_API_KEY or "
            "GEMINI_API_KEY set). Once an administrator configures one, this box will "
            "give you real, personalised explanations instead of this message.",
            False,
        )

    messages = []
    for turn in (history or [])[-MAX_HISTORY_MESSAGES:]:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    user_content = message
    if question_context:
        user_content = f"[Question context]\n{question_context}\n\n[Student's message]\n{message}"
    messages.append({"role": "user", "content": user_content})

    try:
        answer = await _call_ai(TUTOR_SYSTEM_PROMPT, messages)
        return answer, True
    except AIUnavailable as exc:
        logger.warning("Tutor AI call failed: %s", exc)
        return (
            "The tutor is temporarily unavailable (the AI provider could not be reached). "
            "Please try again in a moment.",
            False,
        )


GRADING_SYSTEM_PROMPT = (
    "You are an ACCA DipIFR exam marker. Given a model answer and a student's "
    "answer to the same question, score the student's answer as a percentage "
    "of full marks (0-100) based on accuracy, completeness, and use of correct "
    "IFRS/IAS terminology. Respond with ONLY a JSON object like "
    '{"score_percent": 72, "feedback": "one or two sentences of specific feedback"} '
    "and nothing else."
)


async def grade_answer_with_ai(question_prompt: str, model_answer: str, student_answer: str) -> tuple[int, str] | None:
    """Returns (score_percent, feedback) or None if AI grading is unavailable."""
    if not is_configured():
        return None
    user_message = (
        f"Question:\n{question_prompt}\n\n"
        f"Model answer:\n{model_answer}\n\n"
        f"Student answer:\n{student_answer}"
    )
    try:
        raw = await _call_ai(GRADING_SYSTEM_PROMPT, [{"role": "user", "content": user_message}], max_tokens=300)
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        score = int(parsed["score_percent"])
        score = max(0, min(100, score))
        feedback = str(parsed.get("feedback", "")).strip()
        return score, feedback
    except (AIUnavailable, json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("AI grading failed, falling back to keyword grading: %s", exc)
        return None
