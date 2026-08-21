def _auth_headers(client, email="orderingfix@example.com"):
    client.post("/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = client.post("/auth/login", json={"email": email, "password": "correct-horse-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_question_bank_source_filter_returns_past_exam_questions(client):
    """Regression test: /content/questions previously had no ORDER BY, so
    once the bank grew past the default page size, an entire category
    (real past-exam questions, seeded last and therefore highest-ID) could
    be silently excluded from a plain browse. Filtering explicitly by
    source must always find them regardless of total bank size."""
    headers = _auth_headers(client)
    res = client.get("/content/questions?source=past_exam&limit=100", headers=headers)
    assert res.status_code == 200
    items = res.json()
    # 44 from the original PDF-derived compilation (Dec 2015 - June 2020)
    # + 7 real IAS 16/IAS 23 questions from the user's own study spreadsheet
    # (Dec 2017, June 2018, Sep 2020, Dec 2020, Dec 2021, June 2022, June 2023).
    assert len(items) == 51
    assert all(item["source"] == "past_exam" for item in items)


def test_question_bank_default_browse_is_deterministic(client):
    """Two identical unfiltered requests must return the same set of
    questions in the same order — undefined ordering was the root cause of
    the bug above."""
    headers = _auth_headers(client)
    first = client.get("/content/questions?limit=50", headers=headers).json()
    second = client.get("/content/questions?limit=50", headers=headers).json()
    assert [q["id"] for q in first] == [q["id"] for q in second]


def test_question_bank_supports_flagship_sources(client):
    headers = _auth_headers(client)
    for qtype in ["flagship_core", "flagship_integrated", "flagship_core_2", "flagship_integrated_2"]:
        res = client.get(f"/content/questions?question_type={qtype}&limit=10", headers=headers)
        assert res.status_code == 200
        assert len(res.json()) == 4, f"Expected 4 questions for question_type={qtype}"
