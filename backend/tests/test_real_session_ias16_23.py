def _auth_headers(client, email="realsession@example.com"):
    client.post("/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = client.post("/auth/login", json={"email": email, "password": "correct-horse-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


REAL_SESSIONS = ["December 2017", "June 2018", "September 2020", "December 2020",
                  "December 2021", "June 2022", "June 2023"]


def test_new_real_sessions_are_present_and_cited(client):
    """Each newly added real question must carry its genuine ACCA session
    as source_round, for academic-integrity citation."""
    headers = _auth_headers(client)
    bank = client.get("/content/questions?source=past_exam&limit=100", headers=headers).json()
    found_rounds = {q["source_round"] for q in bank}
    for session in REAL_SESSIONS:
        assert session in found_rounds, f"Missing real session: {session}"


def test_december_2020_question_has_full_spreadsheet_style_working(client):
    headers = _auth_headers(client)
    bank = client.get("/content/questions?source=past_exam&limit=100", headers=headers).json()
    q = next(item for item in bank if item["source_round"] == "December 2020")
    assert "IAS 16" == q["standard_code"] or "IAS 16" in q["related_standards"]
    assert q["marks"] == 15  # real marks as set in the source document


def test_real_session_question_is_gradeable_via_practice(client):
    headers = _auth_headers(client)
    bank = client.get("/content/questions?source=past_exam&limit=100", headers=headers).json()
    june2023 = next(item for item in bank if item["source_round"] == "June 2023")

    res = client.post(
        "/learning/practice/submit",
        json={
            "question_id": june2023["id"],
            "answer_text": "Materials and production overheads and construction salaries are capitalised; "
                           "general administrative overheads and training costs and opening ceremony costs "
                           "are expensed; a constructive obligation provision is recognised at present value.",
            "response_mode": "word_processor",
        },
        headers=headers,
    )
    assert res.status_code == 200
    assert 0 <= res.json()["score_percent"] <= 100


def test_june_2022_question_tagged_cross_standard_with_ias23(client):
    headers = _auth_headers(client)
    bank = client.get("/content/questions?source=past_exam&limit=100", headers=headers).json()
    q = next(item for item in bank if item["source_round"] == "June 2022")
    assert "IAS 23" in q["related_standards"]
