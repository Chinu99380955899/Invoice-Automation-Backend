"""Auth flow: register → login → /me."""


def test_register_and_login_flow(client):
    register_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user1@example.com",
            "full_name": "Test User",
            "password": "Passw0rd!",
            "role": "UPLOADER",
        },
    )
    assert register_resp.status_code == 201, register_resp.text
    assert register_resp.json()["email"] == "user1@example.com"

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "user1@example.com", "password": "Passw0rd!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    assert token

    me_resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "user1@example.com"


def test_login_with_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "user2@example.com",
            "full_name": "Another User",
            "password": "Correct123!",
        },
    )
    bad_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "user2@example.com", "password": "wrong"},
    )
    assert bad_resp.status_code == 401
    assert bad_resp.json()["error_code"] == "INVALID_CREDENTIALS"


def test_me_without_token_is_unauthorized(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
