import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import (
    AIConfirmRequest,
    AIParseResponse,
    AIParseTextRequest,
    CalendarEvent,
    ParsedEventIn,
)
from app.security import get_current_user
from app.services import events as event_service
from app.services import parser_bridge
from app.services import quota

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

router = APIRouter(prefix="/ai", tags=["ai"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]


def _to_response(result) -> AIParseResponse:
    events = [ParsedEventIn.model_validate(item.model_dump()) for item in result.events]
    return AIParseResponse(events=events)


@router.post("/parse-text", response_model=AIParseResponse)
def parse_text(
    payload: AIParseTextRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> AIParseResponse:
    quota.consume_ai_request(db, current_user)
    try:
        result = parser_bridge.parse_text(payload.text, payload.target_date)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return _to_response(result)


@router.post("/parse-image", response_model=AIParseResponse)
async def parse_image(
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
    target_date: Optional[datetime] = Form(default=None),
) -> AIParseResponse:
    quota.consume_ai_request(db, current_user)
    data = await file.read()
    mime = file.content_type or "image/jpeg"
    suffix = ".png" if "png" in mime else ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        result = parser_bridge.parse_image_file(path, target_date)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    finally:
        Path(path).unlink(missing_ok=True)
    return _to_response(result)


@router.post("/confirm", response_model=list[CalendarEvent], status_code=status.HTTP_201_CREATED)
def confirm_parsed_events(
    payload: AIConfirmRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> list[CalendarEvent]:
    created = event_service.create_events_from_parsed(db, current_user, payload.events)
    return [event_service.event_to_schema(row) for row in created]
