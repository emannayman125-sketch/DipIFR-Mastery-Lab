def _auth_headers(client, email="cbeuser@example.com"):
    client.post("/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = client.post("/auth/login", json={"email": email, "password": "correct-horse-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _mock_exam_ids(client):
    exams = client.get("/exams").json()
    core = next(e for e in exams if e["title"] == "Mastery Mock 1 — Core Standards")
    integrated = next(e for e in exams if e["title"] == "Mastery Mock 2 — Integrated Standards")
    return core, integrated


def test_original_mocks_have_exactly_four_questions_each(client):
    """Regression test for the bug where 'Mastery Mock 1' could only match
    one question tagged marks==25 in the whole bank, and 'Mastery Mock 2'
    didn't guarantee 100 total marks either."""
    core, integrated = _mock_exam_ids(client)
    assert core["question_count"] == 4
    assert integrated["question_count"] == 4


def test_original_mocks_total_exactly_100_marks(client):
    headers = _auth_headers(client, email="marks100@example.com")
    core, integrated = _mock_exam_ids(client)
    for exam in (core, integrated):
        started = client.post(f"/exams/{exam['id']}/start", headers=headers).json()
        total = sum(q["marks"] for q in started["exam"]["questions"])
        assert total == 100, f"{exam['title']} totalled {total} marks, expected 100"


def test_integrated_mock_questions_are_genuinely_cross_standard(client):
    headers = _auth_headers(client, email="integrated@example.com")
    _, integrated = _mock_exam_ids(client)
    started = client.post(f"/exams/{integrated['id']}/start", headers=headers).json()
    for q in started["exam"]["questions"]:
        assert len(q["related_standards"]) > 1, f"Question {q['id']} in the Integrated mock isn't cross-standard"


def test_draft_autosave_does_not_grade(client):
    """Autosave must be cheap: it should never trigger grading (keyword or
    AI), only persist the text, so it's safe to call every few seconds
    while a student is still typing."""
    headers = _auth_headers(client, email="draftuser@example.com")
    core, _ = _mock_exam_ids(client)
    started = client.post(f"/exams/{core['id']}/start", headers=headers).json()
    attempt_id = started["attempt_id"]
    qid = started["exam"]["questions"][0]["id"]

    draft = client.post(
        f"/exams/attempts/{attempt_id}/draft",
        json={"question_id": qid, "answer_text": "still working on this...", "response_mode": "word_processor"},
        headers=headers,
    )
    assert draft.status_code == 200
    assert draft.json() == {"saved": True}


def test_finishing_grades_any_ungraded_draft_answers(client):
    """If a student only ever autosaved (draft) the last question and hit
    'Finish' directly, that answer must still be graded at finish time
    rather than silently scoring zero."""
    headers = _auth_headers(client, email="finishdraft@example.com")
    core, _ = _mock_exam_ids(client)
    started = client.post(f"/exams/{core['id']}/start", headers=headers).json()
    attempt_id = started["attempt_id"]
    questions = started["exam"]["questions"]

    # Fully (graded) answer the first three questions.
    for q in questions[:3]:
        client.post(
            f"/exams/attempts/{attempt_id}/answer",
            json={"question_id": q["id"], "answer_text": "A reasonably detailed exam-style answer.", "response_mode": "word_processor"},
            headers=headers,
        )
    # Only draft-save the last one, then finish directly without a final /answer call.
    last_q = questions[3]
    client.post(
        f"/exams/attempts/{attempt_id}/draft",
        json={"question_id": last_q["id"], "answer_text": "A draft-only answer with real content about goodwill and consideration.", "response_mode": "word_processor"},
        headers=headers,
    )

    finished = client.post(f"/exams/attempts/{attempt_id}/finish", headers=headers)
    assert finished.status_code == 200
    assert finished.json()["answered_questions"] == 4

    analysis = client.get(f"/exams/attempts/{attempt_id}/analysis", headers=headers).json()
    last_analysis = next(q for q in analysis["by_question"] if q["question_id"] == last_q["id"])
    # It must have been graded (non-empty feedback), not silently left at 0
    # with the generic "Not answered." placeholder.
    assert last_analysis["feedback"] != "Not answered."


def test_flagship_questions_have_marking_points_summing_to_marks(client):
    """Every flagship (Kit-style) question must expose a real marking-point
    breakdown, and the points must sum to the question's total marks —
    exactly like a real ACCA marking scheme."""
    headers = _auth_headers(client, email="markingpoints@example.com")
    core, integrated = _mock_exam_ids(client)
    for exam in (core, integrated):
        started = client.post(f"/exams/{exam['id']}/start", headers=headers).json()
        attempt_id = started["attempt_id"]
        for q in started["exam"]["questions"]:
            client.post(
                f"/exams/attempts/{attempt_id}/answer",
                json={"question_id": q["id"], "answer_text": "A detailed answer.", "response_mode": "word_processor"},
                headers=headers,
            )
        client.post(f"/exams/attempts/{attempt_id}/finish", headers=headers)
        analysis = client.get(f"/exams/attempts/{attempt_id}/analysis", headers=headers).json()
        for q in analysis["by_question"]:
            assert len(q["marking_points"]) > 0, f"Question {q['question_id']} has no marking points"
            assert sum(mp["marks"] for mp in q["marking_points"]) == q["marks_available"]


def test_exam_analysis_breaks_down_marks_by_standard(client):
    headers = _auth_headers(client, email="analysisuser@example.com")
    core, _ = _mock_exam_ids(client)
    started = client.post(f"/exams/{core['id']}/start", headers=headers).json()
    attempt_id = started["attempt_id"]
    for q in started["exam"]["questions"]:
        client.post(
            f"/exams/attempts/{attempt_id}/answer",
            json={"question_id": q["id"], "answer_text": "A detailed exam-style answer covering the requirement.", "response_mode": "word_processor"},
            headers=headers,
        )
    client.post(f"/exams/attempts/{attempt_id}/finish", headers=headers)

    analysis = client.get(f"/exams/attempts/{attempt_id}/analysis", headers=headers).json()
    assert len(analysis["by_standard"]) > 0
    assert analysis["total_marks"] == 100
    for s in analysis["by_standard"]:
        assert s["marks_available"] > 0


def test_analysis_requires_the_attempt_to_be_finished(client):
    headers = _auth_headers(client, email="notfinished@example.com")
    core, _ = _mock_exam_ids(client)
    started = client.post(f"/exams/{core['id']}/start", headers=headers).json()
    res = client.get(f"/exams/attempts/{started['attempt_id']}/analysis", headers=headers)
    assert res.status_code == 409


def test_spreadsheet_response_mode_is_gradeable(client):
    """A spreadsheet-style answer (serialised as a text table) should still
    reach the grading pipeline like a word-processor answer."""
    headers = _auth_headers(client, email="sheetuser@example.com")
    core, _ = _mock_exam_ids(client)
    started = client.post(f"/exams/{core['id']}/start", headers=headers).json()
    attempt_id = started["attempt_id"]
    qid = started["exam"]["questions"][0]["id"]

    sheet_text = "\tA\tB\n1\tGoodwill\t6400\n2\tNCI\t3400"
    res = client.post(
        f"/exams/attempts/{attempt_id}/answer",
        json={"question_id": qid, "answer_text": sheet_text, "response_mode": "spreadsheet"},
        headers=headers,
    )
    assert res.status_code == 200
    assert 0 <= res.json()["score_percent"] <= 100
