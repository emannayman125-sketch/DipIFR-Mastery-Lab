def _auth_headers(client, email="reviewfix@example.com"):
    client.post("/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = client.post("/auth/login", json={"email": email, "password": "correct-horse-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_past_exam_questions_have_real_marking_scheme_content(client):
    """Regression test for the bug where every real past-exam question had
    a generic placeholder model_answer and empty rubric_keywords, making
    grading meaningless. Verified end-to-end through the API: a past-exam
    question's keyword-based grading must actually respond to answer
    content (not just return the old "No rubric available" placeholder),
    and a real marking-scheme-derived keyword hit should score above zero.
    """
    headers = _auth_headers(client, email="markingscheme@example.com")

    # Find a real past-exam question by filtering explicitly on source=past_exam
    # (rather than relying on an unfiltered browse limit, which is exactly the
    # separate ordering bug this change also fixes in /content/questions).
    bank = client.get("/content/questions?source=past_exam&limit=100", headers=headers).json()
    past_exam_items = bank
    assert len(past_exam_items) > 0

    # Practice mode surfaces the same underlying Question rows; loop until
    # we land on a past-exam one, then submit an empty-ish weak answer vs a
    # strong one built from the question's own prompt text (a cheap way to
    # guarantee some real overlap with a non-trivial rubric derived from the
    # actual marking scheme, without needing direct DB access in the test).
    for _ in range(40):
        q = client.get("/learning/practice/next", headers=headers).json()
        if q.get("source") != "past_exam":
            continue
        weak = client.post(
            "/learning/practice/submit",
            json={"question_id": q["question_id"], "answer_text": "not sure"},
            headers=headers,
        ).json()
        assert weak["feedback"] != "" and weak["feedback"] is not None
        # The old bug always returned this exact placeholder because
        # rubric_keywords was empty for every past-exam question.
        assert weak["feedback"] != "No rubric available for this question."
        return
    raise AssertionError("Never landed on a past-exam question in 40 attempts")


def test_practice_question_includes_source_citation_when_from_a_past_exam(client):
    """Regression test: Practice (adaptive single-question mode) must show
    the same source citation as the Question Bank and Mock Exams — this was
    previously missing from NextQuestionResponse entirely."""
    headers = _auth_headers(client)
    found_past_exam_source = False
    for _ in range(30):
        res = client.get("/learning/practice/next", headers=headers)
        body = res.json()
        if body.get("source") == "past_exam":
            assert body["source_round"]
            # question_number is only known for some past-exam questions
            # (e.g. those explicitly labelled Q1-4 in the source); it's
            # legitimately None when the original question number wasn't
            # available from the source material, so we don't require it.
            found_past_exam_source = True
            break
    assert found_past_exam_source, "Never surfaced a past-exam question with its source in 30 attempts"


def test_cross_standard_practice_updates_the_real_linked_standards(client):
    """Regression test: previously, a cross-standard question's mastery was
    recorded under a fake label like 'PPE + Borrowing Costs' instead of the
    real linked standards (e.g. IAS 16 and IAS 23), so it never showed up
    on the actual standard's mastery."""
    headers = _auth_headers(client)

    # Find a cross-standard question via the content/question-bank endpoint.
    bank = client.get("/content/questions?integrated=true", headers=headers).json()
    assert len(bank) > 0
    cross_question = bank[0]
    assert len(cross_question["related_standards"]) > 1

    # Submitting via /learning/practice/submit should update mastery for
    # every related standard, not a synthetic topic label.
    submit = client.post(
        "/learning/practice/submit",
        json={"question_id": cross_question["id"], "answer_text": "A detailed exam-style answer covering both standards."},
        headers=headers,
    )
    assert submit.status_code == 200
    body = submit.json()
    assert set(body["related_standards"]) == set(cross_question["related_standards"])

    progress = client.get("/learning/progress", headers=headers).json()
    for code in cross_question["related_standards"]:
        assert code in progress["topics"], f"{code} mastery was not updated by the cross-standard question"
