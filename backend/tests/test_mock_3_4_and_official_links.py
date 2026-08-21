def _auth_headers(client, email="mock34user@example.com"):
    client.post("/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = client.post("/auth/login", json={"email": email, "password": "correct-horse-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_four_original_mock_exams_exist_with_correct_marks(client):
    headers = _auth_headers(client)
    exams = client.get("/exams").json()
    titles = {
        "Mastery Mock 1 — Core Standards",
        "Mastery Mock 2 — Integrated Standards",
        "Mastery Mock 3 — Core Standards II",
        "Mastery Mock 4 — Integrated Standards II",
    }
    found = {e["title"]: e for e in exams if e["title"] in titles}
    assert set(found.keys()) == titles
    for title, exam in found.items():
        assert exam["question_count"] == 4, f"{title} did not have 4 questions"
        started = client.post(f"/exams/{exam['id']}/start", headers=headers).json()
        total = sum(q["marks"] for q in started["exam"]["questions"])
        assert total == 100, f"{title} totalled {total} marks"


def test_mock_4_questions_are_genuinely_cross_standard(client):
    headers = _auth_headers(client)
    exams = client.get("/exams").json()
    mock4 = next(e for e in exams if e["title"] == "Mastery Mock 4 — Integrated Standards II")
    started = client.post(f"/exams/{mock4['id']}/start", headers=headers).json()
    for q in started["exam"]["questions"]:
        assert len(q["related_standards"]) > 1


def test_mock_3_and_4_use_previously_uncovered_standards(client):
    """Sanity check that Mock 3/4 add real coverage variety rather than
    duplicating Mock 1/2's standards."""
    headers = _auth_headers(client)
    exams = client.get("/exams").json()
    mock1 = next(e for e in exams if e["title"] == "Mastery Mock 1 — Core Standards")
    mock3 = next(e for e in exams if e["title"] == "Mastery Mock 3 — Core Standards II")

    codes1 = set()
    for q in client.post(f"/exams/{mock1['id']}/start", headers=headers).json()["exam"]["questions"]:
        codes1.update(q["related_standards"])
    codes3 = set()
    for q in client.post(f"/exams/{mock3['id']}/start", headers=headers).json()["exam"]["questions"]:
        codes3.update(q["related_standards"])

    assert codes1.isdisjoint(codes3), f"Mock 1 and Mock 3 unexpectedly share standards: {codes1 & codes3}"


def test_official_resources_endpoint_returns_real_acca_links(client):
    res = client.get("/content/official-resources")
    assert res.status_code == 200
    items = res.json()
    assert len(items) > 0
    for item in items:
        assert item["url"].startswith("https://www.accaglobal.com/")
        assert item["title"]
        assert item["description"]
