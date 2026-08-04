async def test_health(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


async def test_protected_route_requires_auth(client):
    res = await client.get("/api/users/me")
    assert res.status_code == 401


async def test_register_rejects_weak_password(client):
    res = await client.post(
        "/api/auth/register",
        json={
            "email": "a@example.com",
            "username": "weakpwuser",
            "password": "short",
            "password_confirm": "short",
        },
    )
    assert res.status_code == 422
