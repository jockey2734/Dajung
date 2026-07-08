"""Privacy-consent endpoints (webapp-spec S1.5).

개인정보 고지 동의 엔드포인트 (webapp-spec S1.5).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import select

from api.app.core.deps import CurrentUser, SessionDep
from api.app.db.models import PrivacyConsent
from api.app.schemas.chat import PrivacyConsentRequest, PrivacyConsentResponse

router = APIRouter(tags=["privacy"])

PRIVACY_POLICY_VERSION = "2026-07-08"


@router.get("/privacy-consent")
async def get_privacy_consent(current: CurrentUser, session: SessionDep) -> PrivacyConsentResponse:
    row = await session.get(PrivacyConsent, (current.id, PRIVACY_POLICY_VERSION))
    return PrivacyConsentResponse(
        consented=row is not None,
        version=PRIVACY_POLICY_VERSION if row is not None else None,
    )


@router.post("/privacy-consent")
async def post_privacy_consent(
    body: PrivacyConsentRequest, current: CurrentUser, session: SessionDep
) -> PrivacyConsentResponse:
    existing = await session.get(PrivacyConsent, (current.id, body.version))
    if existing is None:
        session.add(
            PrivacyConsent(
                user_id=current.id,
                version=body.version,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
    current_version = (
        await session.execute(
            select(PrivacyConsent.version).where(
                PrivacyConsent.user_id == current.id,
                PrivacyConsent.version == PRIVACY_POLICY_VERSION,
            )
        )
    ).scalar_one_or_none()
    return PrivacyConsentResponse(
        consented=current_version is not None,
        version=current_version,
    )
