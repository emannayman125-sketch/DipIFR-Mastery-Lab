def _auth_headers(client, email="mock56user@example.com"):
    client.post("/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = client.post("/auth/login", json={"email": email, "password": "correct-horse-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_six_original_mock_exams_exist_with_correct_marks(client):
    headers = _auth_headers(client)
    exams = client.get("/exams").json()
    titles = {
        "Mastery Mock 1 — Core Standards",
        "Mastery Mock 2 — Integrated Standards",
        "Mastery Mock 3 — Core Standards II",
        "Mastery Mock 4 — Integrated Standards II",
        "Mastery Mock 5 — Core Standards III",
        "Mastery Mock 6 — Integrated Standards III",
    }
    found = {e["title"]: e for e in exams if e["title"] in titles}
    assert set(found.keys()) == titles
    for title, exam in found.items():
        assert exam["question_count"] == 4, f"{title} did not have 4 questions"
        started = client.post(f"/exams/{exam['id']}/start", headers=headers).json()
        total = sum(q["marks"] for q in started["exam"]["questions"])
        assert total == 100, f"{title} totalled {total} marks"


def test_mock_6_questions_are_genuinely_cross_standard(client):
    headers = _auth_headers(client)
    exams = client.get("/exams").json()
    mock6 = next(e for e in exams if e["title"] == "Mastery Mock 6 — Integrated Standards III")
    started = client.post(f"/exams/{mock6['id']}/start", headers=headers).json()
    for q in started["exam"]["questions"]:
        assert len(q["related_standards"]) > 1


def test_flagship_mocks_now_cover_most_of_the_syllabus(client):
    """Sanity check on overall exam-quality (25-mark, marking-point)
    coverage breadth across all six flagship mocks combined."""
    headers = _auth_headers(client)
    exams = client.get("/exams").json()
    mock_titles = [e for e in exams if e["title"].startswith("Mastery Mock")]
    assert len(mock_titles) == 7

    covered_standards = set()
    for exam in mock_titles:
        started = client.post(f"/exams/{exam['id']}/start", headers=headers).json()
        for q in started["exam"]["questions"]:
            covered_standards.update(q["related_standards"])

    # 22 standards from the first two mock pairs + 11 new ones from the
    # third pair = well over half the 36-item catalog with full exam-style
    # (25-mark, marking-point) questions.
    assert len(covered_standards) >= 30


def test_practice_submit_accepts_response_mode(client):
    headers = _auth_headers(client, email="practicemode@example.com")
    question = client.get("/learning/practice/next", headers=headers).json()
    res = client.post(
        "/learning/practice/submit",
        json={
            "question_id": question["question_id"],
            "answer_text": "\tA\tB\n1\tGoodwill\t6400",
            "response_mode": "spreadsheet",
        },
        headers=headers,
    )
    assert res.status_code == 200
    assert 0 <= res.json()["score_percent"] <= 100


def test_practice_submit_rejects_invalid_response_mode(client):
    headers = _auth_headers(client, email="badmode@example.com")
    question = client.get("/learning/practice/next", headers=headers).json()
    res = client.post(
        "/learning/practice/submit",
        json={"question_id": question["question_id"], "answer_text": "some answer", "response_mode": "not_a_real_mode"},
        headers=headers,
    )
    assert res.status_code == 422
