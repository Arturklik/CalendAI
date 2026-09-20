"""Тесты двусторонней дифференциальной синхронизации (POST /api/v1/sync).

Сценарии:
1. Первичная синхронизация (last_sync=null) — загрузка событий клиента.
2. Вторичная синхронизация — получение серверных изменений.
3. Last-Write-Wins: конфликт разрешается по updated_at.
4. Soft-delete: tombstone передаётся на сервер и другому клиенту.
5. Изоляция и защита от UniqueViolationError при смене аккаунта с чужим id.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient

AuthFactory = Callable[[str, str], Awaitable[dict[str, str]]]
PayloadFactory = Callable[..., dict]


def _future_ts(**kwargs: int) -> str:
    """Метка времени заведомо новее серверных (для победы в LWW)."""
    moment = datetime.now(timezone.utc) + timedelta(**kwargs)
    return moment.isoformat().replace("+00:00", "Z")


async def _sync(
    client: AsyncClient,
    headers: dict[str, str],
    last_sync: str | None,
    changes: list[dict],
) -> dict:
    response = await client.post(
        "/api/v1/sync",
        json={"last_sync_timestamp": last_sync, "client_changes": changes},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_sync_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/sync",
        json={"last_sync_timestamp": None, "client_changes": []},
    )
    assert response.status_code == 401


async def test_initial_sync_uploads_client_events(
    client: AsyncClient,
    register_user: AuthFactory,
    make_event_payload: PayloadFactory,
) -> None:
    headers = await register_user()
    event1 = make_event_payload(title="Матанализ")
    event2 = make_event_payload(title="Физика", event_type="lab")

    body = await _sync(client, headers, None, [event1, event2])

    assert "sync_timestamp" in body
    # Только что принятые события не возвращаются обратно клиенту.
    assert body["server_changes"] == []

    # События сохранились в БД с клиентскими id и updated_at.
    listed = await client.get("/api/v1/events", headers=headers)
    assert listed.status_code == 200
    by_title = {e["title"]: e for e in listed.json()}
    assert set(by_title) == {"Матанализ", "Физика"}
    assert by_title["Матанализ"]["id"] == event1["id"]
    assert by_title["Матанализ"]["updated_at"].startswith("2026-09-08T02:00:00")


async def test_second_sync_returns_server_changes(
    client: AsyncClient,
    register_user: AuthFactory,
    make_event_payload: PayloadFactory,
) -> None:
    headers = await register_user()
    event = make_event_payload()
    first = await _sync(client, headers, None, [event])
    sync_ts = first["sync_timestamp"]

    # Серверное изменение между синками (другой клиент/веб/бот).
    created = await client.post(
        "/api/v1/events",
        json={
            "title": "Серверное событие",
            "event_type": "exam",
            "start_time": "2026-09-10T13:00:00+07:00",
            "end_time": "2026-09-10T14:35:00+07:00",
        },
        headers=headers,
    )
    assert created.status_code == 201
    server_event_id = created.json()["id"]

    second = await _sync(client, headers, sync_ts, [])
    returned_ids = {e["id"] for e in second["server_changes"]}
    # Пришло только серверное событие, старое (не менявшееся) — нет.
    assert returned_ids == {server_event_id}
    assert second["server_changes"][0]["event_type"] == "exam"

    # Пустой третий синк — ничего не возвращает (инкремент чист).
    third = await _sync(client, headers, second["sync_timestamp"], [])
    assert third["server_changes"] == []


async def test_lww_server_version_wins_over_stale_client(
    client: AsyncClient,
    register_user: AuthFactory,
    make_event_payload: PayloadFactory,
) -> None:
    headers = await register_user()
    event = make_event_payload(title="Исходное название")
    first = await _sync(client, headers, None, [event])

    # Серверная правка новее клиентской (через REST, updated_at=now).
    patched = await client.patch(
        f"/api/v1/events/{event['id']}",
        json={"title": "Серверная версия"},
        headers=headers,
    )
    assert patched.status_code == 200

    # Клиент шлёт устаревшую версию — сервер отклоняет её.
    stale = make_event_payload(
        id=event["id"],
        title="Устаревшая клиентская версия",
        updated_at="2026-09-09T00:00:00Z",
    )
    second = await _sync(client, headers, first["sync_timestamp"], [stale])

    server_version = next(
        e for e in second["server_changes"] if e["id"] == event["id"]
    )
    assert server_version["title"] == "Серверная версия"

    current = await client.get(f"/api/v1/events/{event['id']}", headers=headers)
    assert current.json()["title"] == "Серверная версия"


async def test_lww_newer_client_version_wins(
    client: AsyncClient,
    register_user: AuthFactory,
    make_event_payload: PayloadFactory,
) -> None:
    headers = await register_user()
    event = make_event_payload(title="Исходное название")
    first = await _sync(client, headers, None, [event])

    # Клиентская правка новее серверной записи — применяется.
    newer = make_event_payload(
        id=event["id"],
        title="Новая клиентская версия",
        location="Ауд. 500",
        updated_at=_future_ts(minutes=5),
    )
    second = await _sync(client, headers, first["sync_timestamp"], [newer])
    # Принятое событие не дублируется в server_changes.
    assert [e["id"] for e in second["server_changes"]] == []

    current = await client.get(f"/api/v1/events/{event['id']}", headers=headers)
    assert current.json()["title"] == "Новая клиентская версия"
    assert current.json()["location"] == "Ауд. 500"


async def test_soft_delete_propagates_to_other_device(
    client: AsyncClient,
    register_user: AuthFactory,
    make_event_payload: PayloadFactory,
) -> None:
    """Два устройства одного пользователя (общие auth-заголовки)."""
    headers = await register_user()

    # Устройство 1: первичный синк — загружает событие на сервер.
    event = make_event_payload(title="Пара, которую отменили")
    await _sync(client, headers, None, [event])

    # Устройство 2: первичный синк — получает активное событие.
    device2_first = await _sync(client, headers, None, [])
    assert [e["id"] for e in device2_first["server_changes"]] == [event["id"]]
    device2_last_sync = device2_first["sync_timestamp"]

    # Устройство 1: удаляет событие (soft delete) и синхронизируется.
    tombstone = make_event_payload(
        id=event["id"],
        title=event["title"],
        updated_at=_future_ts(minutes=5),
        is_deleted=True,
    )
    await _sync(client, headers, device2_last_sync, [tombstone])

    # Устройство 2: инкрементальный синк — получает tombstone.
    device2_second = await _sync(client, headers, device2_last_sync, [])
    changes = {
        e["id"]: e for e in device2_second["server_changes"]
    }
    assert event["id"] in changes
    assert changes[event["id"]]["is_deleted"] is True


async def test_initial_sync_excludes_deleted_events(
    client: AsyncClient,
    register_user: AuthFactory,
    make_event_payload: PayloadFactory,
) -> None:
    headers = await register_user()
    event = make_event_payload()
    first = await _sync(client, headers, None, [event])

    tombstone = make_event_payload(
        id=event["id"],
        updated_at=_future_ts(minutes=5),
        is_deleted=True,
    )
    await _sync(client, headers, first["sync_timestamp"], [tombstone])

    # «Новое устройство» (last_sync=null) не получает удалённые события.
    fresh = await _sync(client, headers, None, [])
    assert fresh["server_changes"] == []


async def test_sync_isolates_users(
    client: AsyncClient,
    register_user: AuthFactory,
    make_event_payload: PayloadFactory,
) -> None:
    user_a = await register_user("a@example.com")
    user_b = await register_user("b@example.com")

    await _sync(client, user_a, None, [make_event_payload()])

    # Пользователь B не видит события пользователя A.
    body_b = await _sync(client, user_b, None, [])
    assert body_b["server_changes"] == []

    listed_b = await client.get("/api/v1/events", headers=user_b)
    assert listed_b.json() == []


async def test_sync_ignores_foreign_event_id_without_500(
    client: AsyncClient,
    register_user: AuthFactory,
    make_event_payload: PayloadFactory,
) -> None:
    user_a = await register_user("owner@example.com")
    user_b = await register_user("intruder@example.com")

    # Пользователь A создал событие с фиксированным ID.
    event_a = make_event_payload(title="Событие пользователя A")
    await _sync(client, user_a, None, [event_a])

    # Пользователь B пытается прислать событие с ТЕМ ЖЕ самым ID (например, после смены аккаунта на устройстве).
    conflicting_event = make_event_payload(
        id=event_a["id"],
        title="Попытка перезаписи чужого события",
    )
    # Запрос не должен падать с 500 UniqueViolationError, а обязан вернуть 200 OK.
    body_b = await _sync(client, user_b, None, [conflicting_event])
    assert body_b["server_changes"] == []

    # Событие пользователя A не изменилось и не перезаписалось.
    listed_a = await client.get("/api/v1/events", headers=user_a)
    assert listed_a.status_code == 200
    assert listed_a.json()[0]["title"] == "Событие пользователя A"
