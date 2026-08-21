def _auth_headers(client, email="examuser@example.com"):
    client.post("/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = client.post("/auth/login", json={"email": email, "password": "correct-horse-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_exams_returns_seeded_exams(client):
    res = client.get("/exams")
    assert res.status_code == 200
    exams = res.json()
    assert len(exams) >= 2
    assert all(e["question_count"] > 0 for e in exams)


def test_full_exam_attempt_flow(client):
    headers = _auth_headers(client)
    exam_id = client.get("/exams").json()[0]["id"]

    started = client.post(f"/exams/{exam_id}/start", headers=headers)
    assert started.status_code == 200
    attempt = started.json()
    attempt_id = attempt["attempt_id"]
    questions = attempt["exam"]["questions"]
    assert len(questions) > 0

    for q in questions:
        answer_res = client.post(
            f"/exams/attempts/{attempt_id}/answer",
            json={"question_id": q["id"], "answer_text": "A reasonably detailed exam-style answer."},
            headers=headers,
        )
        assert answer_res.status_code == 200
        assert 0 <= answer_res.json()["score_percent"] <= 100

    finished = client.post(f"/exams/attempts/{attempt_id}/finish", headers=headers)
    assert finished.status_code == 200
    body = finished.json()
    assert body["answered_questions"] == len(questions)
    assert body["total_questions"] == len(questions)
    assert 0 <= body["score_percent"] <= 100


def test_cannot_answer_someone_elses_attempt(client):
    headers_a = _auth_headers(client, email="attempt-owner@example.com")
    headers_b = _auth_headers(client, email="attempt-intruder@example.com")
    exam_id = client.get("/exams").json()[0]["id"]

    started = client.post(f"/exams/{exam_id}/start", headers=headers_a).json()
    attempt_id = started["attempt_id"]
    question_id = started["exam"]["questions"][0]["id"]

    res = client.post(
        f"/exams/attempts/{attempt_id}/answer",
        json={"question_id": question_id, "answer_text": "trying to answer someone else's attempt"},
        headers=headers_b,
    )
    assert res.status_code == 404


def test_cannot_resubmit_answer_after_finishing(client):
    headers = _auth_headers(client, email="finisher@example.com")
    exam_id = client.get("/exams").json()[0]["id"]
    started = client.post(f"/exams/{exam_id}/start", headers=headers).json()
    attempt_id = started["attempt_id"]
    question_id = started["exam"]["questions"][0]["id"]

    client.post(
        f"/exams/attempts/{attempt_id}/answer",
        json={"question_id": question_id, "answer_text": "first answer"},
        headers=headers,
    )
    client.post(f"/exams/attempts/{attempt_id}/finish", headers=headers)

    res = client.post(
        f"/exams/attempts/{attempt_id}/answer",
        json={"question_id": question_id, "answer_text": "trying again after finishing"},
        headers=headers,
    )
    assert res.status_code == 409


def test_cannot_answer_question_from_another_exam(client):
    headers = _auth_headers(client, email="exam-boundary@example.com")
    exams = client.get("/exams").json()
    first = client.post(f"/exams/{exams[0]['id']}/start", headers=headers).json()
    second = client.post(f"/exams/{exams[1]['id']}/start", headers=headers).json()
    foreign_question_id = second["exam"]["questions"][0]["id"]
    res = client.post(
        f"/exams/attempts/{first['attempt_id']}/answer",
        json={"question_id": foreign_question_id, "answer_text": "invalid cross-exam answer"},
        headers=headers,
    )
    assert res.status_code == 400
