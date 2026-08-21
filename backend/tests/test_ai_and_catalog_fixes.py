def _auth_headers(client, email="airfixuser@example.com"):
    client.post("/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = client.post("/auth/login", json={"email": email, "password": "correct-horse-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_tutor_accepts_history_and_question_context_without_error(client):
    """Without an API key configured, the tutor still falls back gracefully
    even when history/question_context are supplied — verifies the new
    request schema doesn't break the no-AI-configured path."""
    headers = _auth_headers(client)
    res = client.post(
        "/tutor/ask",
        json={
            "message": "Can you go deeper on that?",
            "history": [
                {"role": "user", "content": "Explain IAS 36 impairment"},
                {"role": "assistant", "content": "IAS 36 requires..."},
            ],
            "question_context": "A machine's carrying amount is $500,000 and recoverable amount is $420,000.",
        },
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["ai_generated"] is False


def test_ias8_title_is_correct_in_standards_catalog(client):
    """Regression test: IAS 8's title was previously the wrong standard's
    description ('Basis of Preparation of Financial Statements') instead of
    its real title."""
    headers = _auth_headers(client)
    standards = client.get("/content/standards", headers=headers).json()
    ias8 = next(s for s in standards if s["code"] == "IAS 8")
    assert ias8["title"] == "Accounting Policies, Changes in Accounting Estimates and Errors"


def test_ethics_and_framework_topic_exists_with_real_questions(client):
    """The syllabus explicitly examines ethics and the Conceptual Framework
    (with a guaranteed 5-mark ethics component in every real Question 2) —
    this had zero coverage before; verify it now has real, non-placeholder
    practice questions."""
    headers = _auth_headers(client)
    standards = client.get("/content/standards", headers=headers).json()
    ethics = next((s for s in standards if s["code"] == "FRAMEWORK-ETHICS"), None)
    assert ethics is not None
    assert ethics["question_count"] >= 2

    bank = client.get("/content/questions?standard=FRAMEWORK-ETHICS", headers=headers).json()
    assert len(bank) >= 2
    assert any("ethic" in q["prompt"].lower() or "ethical" in q["prompt"].lower() for q in bank)
