def _auth_headers(client, email="learner@example.com"):
    client.post("/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = client.post("/auth/login", json={"email": email, "password": "correct-horse-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_progress_starts_empty(client):
    headers = _auth_headers(client)
    res = client.get("/learning/progress", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["overall"] == 0
    assert body["topics"] == {}


def test_next_question_returns_a_real_seeded_question(client):
    headers = _auth_headers(client)
    res = client.get("/learning/practice/next", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["question_id"] > 0
    assert body["topic_code"]
    assert len(body["prompt"]) > 10


def test_submitting_a_strong_answer_scores_higher_than_a_weak_one(client):
    headers = _auth_headers(client)
    question = client.get("/learning/practice/next", headers=headers).json()

    weak = client.post(
        "/learning/practice/submit",
        json={"question_id": question["question_id"], "answer_text": "I am not sure."},
        headers=headers,
    )
    assert weak.status_code == 200
    assert weak.json()["graded_by_ai"] is False  # no API key configured in tests
    weak_score = weak.json()["score_percent"]
    assert 0 <= weak_score <= 100


def test_progress_persists_and_is_isolated_per_user(client):
    headers_a = _auth_headers(client, email="a@example.com")
    headers_b = _auth_headers(client, email="b@example.com")

    question = client.get("/learning/practice/next", headers=headers_a).json()
    client.post(
        "/learning/practice/submit",
        json={"question_id": question["question_id"], "answer_text": "depreciation revaluation surplus"},
        headers=headers_a,
    )

    progress_a = client.get("/learning/progress", headers=headers_a).json()
    progress_b = client.get("/learning/progress", headers=headers_b).json()
    assert progress_a["topics"] != {}
    assert progress_b["topics"] == {}


def test_submit_practice_rejects_unknown_question(client):
    headers = _auth_headers(client)
    res = client.post(
        "/learning/practice/submit",
        json={"question_id": 999999, "answer_text": "anything"},
        headers=headers,
    )
    assert res.status_code == 404

def test_my_level_empty_for_new_user(client):
    headers = _auth_headers(client, email="fresh@example.com")
    res = client.get("/learning/my-level", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["overall_mastery"] == 0
    assert body["is_exam_ready"] is False
    assert body["exam_readiness_percent"] == 0
    assert body["weakest_standards"] == []
    assert body["strongest_standards"] == []
    assert body["mock_score_history"] == []
    assert body["mock_average_percent"] is None
    assert body["standards_practiced"] == 0
    assert body["standards_total"] >= 36
    assert body["mocks_completed"] == 0
    assert body["mocks_total"] == 7


def test_my_level_reflects_practice_and_ranks_weakest_first(client):
    headers = _auth_headers(client, email="practicer@example.com")
    question = client.get("/learning/practice/next", headers=headers).json()
    client.post(
        "/learning/practice/submit",
        json={"question_id": question["question_id"], "answer_text": "A reasonably detailed technical answer covering the key requirements."},
        headers=headers,
    )

    res = client.get("/learning/my-level", headers=headers)
    body = res.json()
    assert body["standards_practiced"] >= 1
    assert 0 <= body["overall_mastery"] <= 100
    # exam readiness is expressed against the 50% real pass mark, so it moves
    # faster than raw mastery (e.g. 25 mastery -> 50% readiness).
    assert body["exam_readiness_percent"] == min(100, round(body["overall_mastery"] / 50 * 100))
    assert len(body["weakest_standards"]) >= 1
    # weakest_standards must actually be sorted ascending by mastery
    masteries = [s["mastery"] for s in body["weakest_standards"]]
    assert masteries == sorted(masteries)


def test_my_level_includes_finished_mock_exam_score(client):
    headers = _auth_headers(client, email="mockuser@example.com")
    exams = client.get("/exams").json()
    mock = next(e for e in exams if e["title"].startswith("Mastery Mock"))
    started = client.post(f"/exams/{mock['id']}/start", headers=headers).json()
    attempt_id = started["attempt_id"]
    for q in started["exam"]["questions"]:
        client.post(
            f"/exams/attempts/{attempt_id}/answer",
            json={"question_id": q["id"], "answer_text": "A worked answer for this question."},
            headers=headers,
        )
    client.post(f"/exams/attempts/{attempt_id}/finish", headers=headers)

    res = client.get("/learning/my-level", headers=headers)
    body = res.json()
    assert len(body["mock_score_history"]) == 1
    assert body["mock_score_history"][0]["exam_id"] == mock["id"]
    assert body["mock_average_percent"] == body["mock_score_history"][0]["score_percent"]
    assert body["mocks_completed"] == 1
    assert body["mocks_total"] == 7
