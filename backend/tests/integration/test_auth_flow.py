"""Codifies the manual end-to-end verification from 2026-08-04 (see
requirements-definition.md §10 確定事項20), which is how three real
runtime bugs were originally found: a notification-email failure
blocking registration, timezone-naive datetime columns, and JWT
collisions when two tokens were issued for the same user within the
same second. Having this as an automated test is what would have
caught all three immediately instead of needing manual discovery."""

REGISTER_PAYLOAD = {
    "email": "authflow@example.com",
    "username": "authflowuser",
    "password": "Test1234!",
    "password_confirm": "Test1234!",
}


async def test_register_then_immediate_login_does_not_collide(client):
    """Regression test for the JWT `jti`-less collision bug: two tokens
    issued for the same user within the same wall-clock second used to
    violate RefreshToken.token_hash's unique constraint."""
    register_res = await client.post("/api/auth/register", json=REGISTER_PAYLOAD)
    assert register_res.status_code == 201
    assert "access_token" in register_res.json()

    login_res = await client.post(
        "/api/auth/login",
        json={"identifier": "authflowuser", "password": "Test1234!"},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()


async def test_full_auth_lifecycle(client):
    register_res = await client.post("/api/auth/register", json=REGISTER_PAYLOAD)
    token = register_res.json()["access_token"]

    me_res = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "authflowuser"

    refresh_res = await client.post("/api/auth/refresh")
    assert refresh_res.status_code == 200
    assert "access_token" in refresh_res.json()

    logout_res = await client.post("/api/auth/logout")
    assert logout_res.status_code == 200

    # Refresh token was revoked by logout — a further refresh must fail.
    refresh_after_logout = await client.post("/api/auth/refresh")
    assert refresh_after_logout.status_code == 401

    # The access token itself is still valid until it naturally expires —
    # logout only revokes the refresh token, not already-issued access
    # tokens (§5: short-lived by design instead).
    me_after_logout = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me_after_logout.status_code == 200


async def test_forgot_password_is_enumeration_safe(client):
    """§11.2: the response must be identical whether or not the account
    exists — and must not 500 just because the email provider has no key
    configured in this test environment (regression test for the
    email-failure-blocks-the-request bug)."""
    await client.post("/api/auth/register", json=REGISTER_PAYLOAD)

    existing_res = await client.post(
        "/api/auth/forgot-password", json={"email": REGISTER_PAYLOAD["email"]}
    )
    nonexistent_res = await client.post(
        "/api/auth/forgot-password", json={"email": "nobody@example.com"}
    )

    assert existing_res.status_code == 200
    assert nonexistent_res.status_code == 200
    assert existing_res.json() == nonexistent_res.json()


async def test_account_deletion_cascades(client):
    register_res = await client.post("/api/auth/register", json=REGISTER_PAYLOAD)
    token = register_res.json()["access_token"]

    delete_res = await client.delete("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert delete_res.status_code == 200

    # The same access token must no longer resolve to a user.
    me_res = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 401
