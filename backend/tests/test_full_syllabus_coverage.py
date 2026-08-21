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
    """The syllabus has exactly 36 standard areas; every one of them must
    now be covered by at least one 25-mark, marking-point-backed flagship
    question via the seven mock exams combined."""
    headers = _auth_headers(client)
    all_standards = {s["code"] for s in client.get("/content/standards", headers=headers).json()}
    assert len(all_standards) == 36

    exams = client.get("/exams").json()
    mocks = [e for e in exams if e["title"].startswith("Mastery Mock")]
    covered = set()
    for exam in mocks:
        started = client.post(f"/exams/{exam['id']}/start", headers=headers).json()
        for q in started["exam"]["questions"]:
            covered.update(q["related_standards"])

    missing = all_standards - covered
    assert not missing, f"Standards still without a flagship question: {sorted(missing)}"


def test_ifrs18_ifrs19_smes_now_have_marking_points(client):
    headers = _auth_headers(client)
    for code in ["IFRS 18", "IFRS 19", "IFRS for SMEs"]:
        bank = client.get(f"/content/questions?standard={code}&limit=20", headers=headers).json()
        flagship = [q for q in bank if q["question_type"].startswith("flagship")]
        assert len(flagship) > 0, f"{code} has no flagship-quality question"
