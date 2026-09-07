from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import SubscriptionPlan, User, utcnow, week_reset_at

WEEKLY_AI_LIMITS = {
    SubscriptionPlan.FREE: 0,
    SubscriptionPlan.PLUS: 7,
    SubscriptionPlan.PRO: 70,
}


def remaining_quota(user: User) -> int:
    _maybe_reset(user)
    limit = WEEKLY_AI_LIMITS[user.subscription_tier]
    return max(0, limit - user.ai_requests_this_week)


def consume_ai_request(db: Session, user: User) -> None:
    from app.config import get_settings

    if get_settings().ai_stub:
        return

    _maybe_reset(user)
    limit = WEEKLY_AI_LIMITS[user.subscription_tier]
    if limit <= 0 or user.ai_requests_this_week >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "AI quota exceeded for this week. "
                f"Plan '{user.subscription_tier.value}' allows {limit} requests."
            ),
        )
    user.ai_requests_this_week += 1
    db.add(user)
    db.commit()
    db.refresh(user)


def _maybe_reset(user: User) -> None:
    if user.week_reset_at <= utcnow():
        user.ai_requests_this_week = 0
        user.week_reset_at = week_reset_at()
