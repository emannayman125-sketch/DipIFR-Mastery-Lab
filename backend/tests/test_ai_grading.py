import asyncio
import json
from unittest.mock import AsyncMock, patch

from app.core import ai_client


def test_grade_answer_with_ai_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(ai_client.settings, "anthropic_api_key", "")
    monkeypatch.setattr(ai_client.settings, "gemini_api_key", "")
    result = asyncio.run(ai_client.grade_answer_with_ai("Q", "model answer", "student answer"))
    assert result is None


def test_grade_answer_with_ai_includes_marking_scheme_in_prompt(monkeypatch):
    """The formal per-criterion marking scheme (already stored as
    QuestionCriterion rows and shown to students after grading) must
    actually reach the AI grader, not just get thrown away after seeding —
    that was the bug this change fixes."""
    monkeypatch.setattr(ai_client.settings, "anthropic_api_key", "fake-key")
    monkeypatch.setattr(ai_client.settings, "gemini_api_key", "")

    captured = {}

    async def fake_call_ai(system, messages, max_tokens=600, retries=1):
        captured["system"] = system
        captured["user_message"] = messages[0]["content"]
        return json.dumps({"score_percent": 80, "feedback": "Good coverage of the criteria."})

    with patch.object(ai_client, "_call_ai", new=AsyncMock(side_effect=fake_call_ai)):
        criteria = [
            ("Depreciation add-back explained", 5, "Non-cash expense reasoning"),
            ("Cash generated from operations calculated correctly", 8, "$22.1 million"),
        ]
        result = asyncio.run(
            ai_client.grade_answer_with_ai("Q text", "Model answer text", "Student's answer", criteria)
        )

    assert result == (80, "Good coverage of the criteria.")
    # The marking scheme must be visible in what was actually sent to the AI.
    assert "Formal marking scheme (13 marks total)" in captured["user_message"]
    assert "Depreciation add-back explained (5 of 13 marks)" in captured["user_message"]
    assert "Cash generated from operations calculated correctly (8 of 13 marks)" in captured["user_message"]
    assert "$22.1 million" in captured["user_message"]
    # The system prompt must instruct point-by-point, figure-checking marking.
    assert "EACH criterion individually" in captured["system"]


def test_grade_answer_with_ai_without_criteria_has_no_marking_scheme_section(monkeypatch):
    monkeypatch.setattr(ai_client.settings, "anthropic_api_key", "fake-key")
    monkeypatch.setattr(ai_client.settings, "gemini_api_key", "")

    captured = {}

    async def fake_call_ai(system, messages, max_tokens=600, retries=1):
        captured["user_message"] = messages[0]["content"]
        return json.dumps({"score_percent": 50, "feedback": "Partial answer."})

    with patch.object(ai_client, "_call_ai", new=AsyncMock(side_effect=fake_call_ai)):
        result = asyncio.run(
            ai_client.grade_answer_with_ai("Q text", "Model answer text", "Student's answer")
        )

    assert result == (50, "Partial answer.")
    assert "Formal marking scheme" not in captured["user_message"]
