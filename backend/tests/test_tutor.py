def _auth_headers(client, email="tutoruser@example.com"):
    client.post("/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = client.post("/auth/login", json={"email": email, "password": "correct-horse-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_tutor_requires_auth(client):
    res = client.post("/tutor/ask", json={"message": "Explain IAS 36"})
    assert res.status_code == 401


def test_tutor_falls_back_gracefully_without_api_key(client):
    headers = _auth_headers(client)
    res = client.post("/tutor/ask", json={"message": "Explain impairment of assets"}, headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["ai_generated"] is False
    assert "AI tutor" in body["reply"] or "ANTHROPIC" in body["reply"].upper() or len(body["reply"]) > 0
