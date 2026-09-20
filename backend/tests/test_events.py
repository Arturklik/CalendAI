"""Тесты REST CRUD для /api/v1/events."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from httpx import AsyncClient


def _event_payload(**overrides: object) -> dict:
    payload = {
        "title": "Лекция: Математический анализ",
        "event_type": "lecture",
        "start_time": "2026-09-08T09:00:00+07:00",
        "end_time": "2026-09-08T10:35:00+07:00",
        "location": "Ауд. 214",
        "teacher": "Иванов А.П.",
        "description": None,
        "recurrence_rule": "FREQ=WEEKLY;INTERVAL=1",
    }
    payload.update(overrides)
    return payload


async def test_create_event(
    client: AsyncClient,
    register_user: Callable[[str, str], Awaitable[dict[str, str]]],
) -> None:
    headers = await register_user()
    response = await client.post(
        "/api/v1/events", json=_event_payload(), headers=headers
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["title"] == "Лекция: Математический анализ"
    assert body["event_type"] == "lecture"
    # Сервер проставляет updated_at и нормализует время к UTC.
    assert body["updated_at"] is not None
    assert body["start_time"].endswith("+00:00") or body["start_time"].endswith("Z")
    assert body["is_deleted"] is False
    uuid.UUID(body["id"])  # валидный UUID


async def test_create_event_end_before_start_rejected(
    client: AsyncClient,
    register_user: Callable[[str, str], Awaitable[dict[str, str]]],
) -> None:
    headers = await register_user()
    response = await client.post(
        "/api/v1/events",
        json=_event_payload(
            start_time="2026-09-08T10:35:00+07:00",
            end_time="2026-09-08T09:00:00+07:00",
        ),
        headers=headers,
    )
    assert response.status_code == 422


async def test_list_events_only_own(
    client: AsyncClient,
    register_user: Callable[[str, str], Awaitable[dict[str, str]]],
) -> None:
    owner = await register_user("owner@example.com")
    stranger = await register_user("stranger@example.com")

    await client.post("/api/v1/events", json=_event_payload(), headers=owner)

    own = await client.get("/api/v1/events", headers=owner)
    assert own.status_code == 200
    assert len(own.json()) == 1

    foreign = await client.get("/api/v1/events", headers=stranger)
    assert foreign.status_code == 200
    assert foreign.json() == []


async def test_get_and_patch_event(
    client: AsyncClient,
    register_user: Callable[[str, str], Awaitable[dict[str, str]]],
) -> None:
    headers = await register_user()
    created = await client.post(
        "/api/v1/events", json=_event_payload(), headers=headers
    )
    event_id = created.json()["id"]
    created_updated_at = created.json()["updated_at"]

    got = await client.get(f"/api/v1/events/{event_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["location"] == "Ауд. 214"

    patched = await client.patch(
        f"/api/v1/events/{event_id}",
        json={"location": "Ауд. 100", "teacher": None},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["location"] == "Ауд. 100"
    assert body["teacher"] is None  # явный null очищает поле
    assert body["title"] == "Лекция: Математический анализ"  # не изменилось
    assert body["updated_at"] >= created_updated_at


async def test_patch_event_breaking_time_invariant_rejected(
    client: AsyncClient,
    register_user: Callable[[str, str], Awaitable[dict[str, str]]],
) -> None:
    headers = await register_user()
    created = await client.post(
        "/api/v1/events", json=_event_payload(), headers=headers
    )
    event_id = created.json()["id"]

    patched = await client.patch(
        f"/api/v1/events/{event_id}",
        json={"end_time": "2026-09-08T08:00:00+07:00"},
        headers=headers,
    )
    assert patched.status_code == 422


async def test_delete_event_soft(
    client: AsyncClient,
    register_user: Callable[[str, str], Awaitable[dict[str, str]]],
) -> None:
    headers = await register_user()
    created = await client.post(
        "/api/v1/events", json=_event_payload(), headers=headers
    )
    event_id = created.json()["id"]

    deleted = await client.delete(f"/api/v1/events/{event_id}", headers=headers)
    assert deleted.status_code == 204

    # Запись осталась (soft delete), но скрыта из списка по умолчанию.
    got = await client.get(f"/api/v1/events/{event_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["is_deleted"] is True

    listed = await client.get("/api/v1/events", headers=headers)
    assert listed.json() == []

    with_deleted = await client.get(
        "/api/v1/events?include_deleted=true", headers=headers
    )
    assert len(with_deleted.json()) == 1


async def test_foreign_event_not_found(
    client: AsyncClient,
    register_user: Callable[[str, str], Awaitable[dict[str, str]]],
) -> None:
    owner = await register_user("owner2@example.com")
    stranger = await register_user("stranger2@example.com")

    created = await client.post(
        "/api/v1/events", json=_event_payload(), headers=owner
    )
    event_id = created.json()["id"]

    for method in ("get", "patch", "delete"):
        request = getattr(client, method)
        kwargs = {"headers": stranger}
        if method == "patch":
            kwargs["json"] = {"title": "Взлом"}
        response = await request(f"/api/v1/events/{event_id}", **kwargs)
        assert response.status_code == 404, method


async def test_events_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/events")).status_code == 401
    assert (
        await client.post("/api/v1/events", json=_event_payload())
    ).status_code == 401
