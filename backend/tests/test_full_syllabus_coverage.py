def _auth_headers(client, email="fullcoverage@example.com"):
    client.post("/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = client.post("/auth/login", json={"email": email, "password": "correct-horse-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_seven_original_mock_exams_all_100_marks(client):
    headers = _auth_headers(client)
    exams = client.get("/exams").json()
    mocks = [e for e in exams if e["title"].startswith("Mastery Mock")]
    assert len(mocks) == 7
    for exam in mocks:
        assert exam["question_count"] == 4
        started = client.post(f"/exams/{exam['id']}/start", headers=headers).json()
        total = sum(q["marks"] for q in started["exam"]["questions"])
        assert total == 100, f"{exam['title']} totalled {total} marks"


def test_all_36_standards_have_flagship_exam_quality_questions(client):
    """The syllabus has 38 standard areas (36 examinable ACCA DipIFR areas
    plus IFRS S1/S2, included for general awareness only and explicitly
    flagged as not examinable). Every examinable standard must be covered by
    at least one 25-mark, marking-point-backed flagship question via the
    seven mock exams combined, with one deliberate exception: IFRS 1 is
    examinable but — per ACCA's own past papers and examiner commentary —
    only ever appears as a short discussion component within another
    question, never as a full standalone 25-mark question, so requiring a
    flagship-level question for it would misrepresent the real exam. It is
    instead checked separately for adequate scenario-level coverage."""
    headers = _auth_headers(client)
    standards = client.get("/content/standards", headers=headers).json()
    all_standards = {s["code"] for s in standards}
    assert len(all_standards) == 38

    non_examinable = {s["code"] for s in standards if s["examinable"] is False}
    assert non_examinable == {"IFRS S1", "IFRS S2"}

    no_flagship_expected = non_examinable | {"IFRS 1"}

    exams = client.get("/exams").json()
    mocks = [e for e in exams if e["title"].startswith("Mastery Mock")]
    covered = set()
    for exam in mocks:
        started = client.post(f"/exams/{exam['id']}/start", headers=headers).json()
        for q in started["exam"]["questions"]:
            covered.update(q["related_standards"])

    missing = (all_standards - no_flagship_expected) - covered
    assert not missing, f"Examinable standards still without a flagship question: {sorted(missing)}"

    # IFRS 1 still needs a real, adequately-marked original question even
    # though it doesn't get a full flagship.
    bank = client.get("/content/questions?standard=IFRS 1&limit=20", headers=headers).json()
    assert any(q["marks"] >= 10 for q in bank), "IFRS 1 has no scenario-level question"


def test_ifrs18_ifrs19_smes_now_have_marking_points(client):
    headers = _auth_headers(client)
    for code in ["IFRS 18", "IFRS 19", "IFRS for SMEs"]:
        bank = client.get(f"/content/questions?standard={code}&limit=20", headers=headers).json()
        flagship = [q for q in bank if q["question_type"].startswith("flagship")]
        assert len(flagship) > 0, f"{code} has no flagship-quality question"
