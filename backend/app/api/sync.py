from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import SyncRequest, SyncResponse
from app.security import get_current_user
from app.services import events as event_service

router = APIRouter(tags=["sync"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]


@router.post("/sync", response_model=SyncResponse)
def sync(
    payload: SyncRequest,
    current_user: CurrentUser,
    db: DbSession,
    x_device_id: Annotated[Optional[str], Header()] = None,
) -> SyncResponse:
    """
    Differential sync contract from the project PDF:
    POST /api/v1/sync with last_sync_timestamp + client_changes.
    """
    sync_timestamp, server_changes = event_service.sync_events(
        db,
        current_user,
        last_sync_timestamp=payload.last_sync_timestamp,
        client_changes=payload.client_changes,
        device_id=x_device_id,
    )
    return SyncResponse(sync_timestamp=sync_timestamp, server_changes=server_changes)
