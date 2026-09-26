"""Тесты endpoint распознавания голосовых расписаний."""

from __future__ import annotations

from datetime import date

import pytest
from app.services import ai_service
from httpx import AsyncClient

from ai_module import ScheduleParseResponse


async def test_parse_voice_transcribes_and_parses_schedule(
    client: AsyncClient,
    register_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = await register_user("voice@example.com")
    calls: dict[str, object] = {}

    async def fake_transcribe(audio_bytes: bytes, filename: str) -> str:
        calls["audio_bytes"] = audio_bytes
        calls["filename"] = filename
        return "В понедельник математика в аудитории 214"

    async def fake_parse(text: str, base_date: date, timezone_offset: str):
        calls["text"] = text
        calls["base_date"] = base_date
        calls["timezone_offset"] = timezone_offset
        return ScheduleParseResponse(events=[])

    monkeypatch.setattr(ai_service, "transcribe_audio", fake_transcribe)
    monkeypatch.setattr(ai_service, "parse_schedule_text", fake_parse)

    response = await client.post(
        "/api/v1/ai/parse-voice",
        params={"base_date": "2026-09-26", "tz": "+07:00"},
        files={"file": ("schedule.webm", b"audio-data", "audio/webm")},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"events": []}
    assert calls == {
        "audio_bytes": b"audio-data",
        "filename": "schedule.webm",
        "text": "В понедельник математика в аудитории 214",
        "base_date": date(2026, 9, 26),
        "timezone_offset": "+07:00",
    }


async def test_parse_voice_rejects_unsupported_extension(
    client: AsyncClient,
    register_user,
) -> None:
    headers = await register_user("voice-invalid@example.com")
    response = await client.post(
        "/api/v1/ai/parse-voice",
        params={"base_date": "2026-09-26"},
        files={"file": ("schedule.txt", b"not audio", "text/plain")},
        headers=headers,
    )
    assert response.status_code == 415


async def test_parse_voice_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/ai/parse-voice",
        params={"base_date": "2026-09-26"},
        files={"file": ("schedule.mp3", b"audio-data", "audio/mpeg")},
    )
    assert response.status_code == 401
