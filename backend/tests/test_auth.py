def test_register_returns_access_token_and_sets_refresh_cookie(client):
    res = client.post(
        "/auth/register",
        json={"email": "student@example.com", "password": "correct-horse-1", "display_name": "Sara"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    # The refresh token must never appear in the JSON body — only as an
    # HttpOnly cookie.
    assert "refresh_token" not in body
    assert "dipifr_refresh_token" in res.cookies
    set_cookie_header = res.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie_header


def test_register_duplicate_email_rejected(client):
    payload = {"email": "dup@example.com", "password": "correct-horse-1"}
    first = client.post("/auth/register", json=payload)
    second = client.post("/auth/register", json=payload)
    assert first.status_code == 201
    assert second.status_code == 409


def test_login_with_correct_credentials(client):
    client.post("/auth/register", json={"email": "login@example.com", "password": "correct-horse-1"})
    res = client.post("/auth/login", json={"email": "login@example.com", "password": "correct-horse-1"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_with_wrong_password_rejected(client):
    client.post("/auth/register", json={"email": "wrong@example.com", "password": "correct-horse-1"})
    res = client.post("/auth/login", json={"email": "wrong@example.com", "password": "not-the-password"})
    assert res.status_code == 401


def test_protected_endpoint_requires_token(client):
    res = client.get("/learning/progress")
    assert res.status_code == 401


def test_protected_endpoint_rejects_garbage_token(client):
    res = client.get("/learning/progress", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


def test_refresh_rotates_token_and_old_one_stops_working(client):
    reg = client.post("/auth/register", json={"email": "refresh@example.com", "password": "correct-horse-1"})
    old_refresh = client.cookies.get("dipifr_refresh_token")
    old_access = reg.json()["access_token"]

    refreshed = client.post("/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"] != old_access
    new_refresh = client.cookies.get("dipifr_refresh_token")
    assert new_refresh != old_refresh

    # Replay the old (now-rotated-away) refresh cookie explicitly.
    reused = client.post("/auth/refresh", cookies={"dipifr_refresh_token": old_refresh})
    assert reused.status_code == 401


def test_refresh_without_cookie_rejected(client):
    res = client.post("/auth/refresh")
    assert res.status_code == 401


def test_logout_revokes_refresh_token(client):
    client.post("/auth/register", json={"email": "logout@example.com", "password": "correct-horse-1"})
    refresh_token = client.cookies.get("dipifr_refresh_token")

    logout_res = client.post("/auth/logout")
    assert logout_res.status_code == 204

    reuse = client.post("/auth/refresh", cookies={"dipifr_refresh_token": refresh_token})
    assert reuse.status_code == 401


def test_forgot_password_always_returns_generic_message(client):
    known = client.post("/auth/password/forgot", json={"email": "unknown-nobody@example.com"})
    assert known.status_code == 200
    assert "detail" in known.json()


def test_password_reset_flow(client, monkeypatch):
    captured = {}

    def fake_send(to, reset_url):
        captured["url"] = reset_url

    monkeypatch.setattr("app.api.auth.send_password_reset_email", fake_send)

    client.post("/auth/register", json={"email": "resetme@example.com", "password": "old-password-1"})
    client.post("/auth/password/forgot", json={"email": "resetme@example.com"})
    assert "url" in captured

    token = captured["url"].split("token=")[1]
    reset_res = client.post("/auth/password/reset", json={"token": token, "new_password": "new-password-1"})
    assert reset_res.status_code == 200

    old_login = client.post("/auth/login", json={"email": "resetme@example.com", "password": "old-password-1"})
    assert old_login.status_code == 401

    new_login = client.post("/auth/login", json={"email": "resetme@example.com", "password": "new-password-1"})
    assert new_login.status_code == 200


def test_email_verification_flow(client, monkeypatch):
    captured = {}

    def fake_send(to, verify_url):
        captured["url"] = verify_url

    monkeypatch.setattr("app.api.auth.send_verification_email", fake_send)

    client.post("/auth/register", json={"email": "verifyme@example.com", "password": "correct-horse-1"})
    assert "url" in captured

    token = captured["url"].split("token=")[1]
    res = client.post("/auth/verify-email", json={"token": token})
    assert res.status_code == 200


def test_password_reset_token_is_single_use(client, monkeypatch):
    captured = {}
    monkeypatch.setattr("app.api.auth.send_password_reset_email", lambda to, reset_url: captured.setdefault("url", reset_url))
    client.post("/auth/register", json={"email": "single-use@example.com", "password": "old-password-1"})
    client.post("/auth/password/forgot", json={"email": "single-use@example.com"})
    token = captured["url"].split("token=", 1)[1]
    assert client.post("/auth/password/reset", json={"token": token, "new_password": "new-password-1"}).status_code == 200
    assert client.post("/auth/password/reset", json={"token": token, "new_password": "new-password-2"}).status_code == 400


def test_email_verification_token_is_single_use(client, monkeypatch):
    captured = {}
    monkeypatch.setattr("app.api.auth.send_verification_email", lambda to, verify_url: captured.setdefault("url", verify_url))
    client.post("/auth/register", json={"email": "single-verify@example.com", "password": "correct-horse-1"})
    token = captured["url"].split("token=", 1)[1]
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 400
