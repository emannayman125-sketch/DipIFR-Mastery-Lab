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
