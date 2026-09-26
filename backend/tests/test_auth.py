"""Тесты аутентификации: регистрация, логин, JWT, /me."""

from __future__ import annotations

from httpx import AsyncClient


async def test_register_success(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "student@example.com", "password": "secret123"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "student@example.com"
    assert body["subscription_tier"] == "free"
    assert body["telegram_id"] is None
    assert "id" in body and "created_at" in body
    assert "password" not in body and "password_hash" not in body


async def test_register_duplicate_email_conflict(client: AsyncClient) -> None:
    payload = {"email": "dup@example.com", "password": "secret123"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


async def test_register_short_password_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "weak@example.com", "password": "short"},
    )
    assert response.status_code == 422


async def test_login_success_and_me(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "secret123"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "secret123"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    assert login.json()["token_type"] == "bearer"

    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "login@example.com"


async def test_login_wrong_password(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wrong@example.com", "password": "secret123"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@example.com", "password": "other-pass"},
    )
    assert login.status_code == 401


async def test_me_without_token_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_with_garbage_token_unauthorized(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer garbage"}
    )
    assert response.status_code == 401


async def test_change_password_success(
    client: AsyncClient,
    register_user,
) -> None:
    headers = await register_user("change-password@example.com", "secret123")
    changed = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "secret123", "new_password": "new-secret456"},
        headers=headers,
    )
    assert changed.status_code == 200, changed.text
    assert changed.json() == {
        "status": "ok",
        "message": "Password changed successfully",
    }

    old_password = await client.post(
        "/api/v1/auth/login",
        json={"email": "change-password@example.com", "password": "secret123"},
    )
    new_password = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "change-password@example.com",
            "password": "new-secret456",
        },
    )
    assert old_password.status_code == 401
    assert new_password.status_code == 200


async def test_change_password_rejects_incorrect_current_password(
    client: AsyncClient,
    register_user,
) -> None:
    headers = await register_user("change-password-wrong@example.com")
    response = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "wrong-pass", "new_password": "new-secret456"},
        headers=headers,
    )
    assert response.status_code == 400


async def test_change_password_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "secret123", "new_password": "new-secret456"},
    )
    assert response.status_code == 401


async def test_telegram_link_token_requires_auth(client: AsyncClient) -> None:
    anon = await client.post("/api/v1/auth/telegram-link-token")
    assert anon.status_code == 401

    await client.post(
        "/api/v1/auth/register",
        json={"email": "tg@example.com", "password": "secret123"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "tg@example.com", "password": "secret123"},
    )
    token = login.json()["access_token"]
    response = await client.post(
        "/api/v1/auth/telegram-link-token",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["link_token"]
    assert body["expires_in_seconds"] > 0
