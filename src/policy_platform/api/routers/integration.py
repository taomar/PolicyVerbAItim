"""Integration: issuing and revoking the API subscription keys a caller uses.

WHY THIS EXISTS SEPARATELY FROM THE CONFIGURED KEY

`POLICY_SUBSCRIPTION_KEY` is an environment value. Changing it means editing a
file and restarting the API, there is no overlap window, and every caller using
the old value breaks at the instant of the restart. That is adequate for one
operator with one integration and inadequate the moment a second one exists.
These endpoints let an administrator issue a key, run both for as long as it
takes to move the caller across, and then revoke the old one.

WHY THE WHOLE ROUTER IS GATED ON `local`

Where an API gateway fronts this deployment, the gateway owns caller
subscriptions and its policy rewrites the subscription-key header with its own
backend credential before the request arrives. A key issued here would be
discarded in transit, so the screen would be offering to manage a credential
this deployment does not control. Every endpoint checks, not just the menu that
leads here: a hidden menu item is a convenience, and the refusal is the control.

The check reads the setting per request rather than at import, so a deployment
that changes shape does not need this module reloaded to notice.

WHAT IS NEVER RETURNED

The key, after the call that generates it. Only a hash is stored, so there is
nothing to return — the list endpoint could not disclose one if it tried, which
is the property that makes this table safe to read from an admin screen.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from policy_platform.api.authz import Principal, get_principal
from policy_platform.domain.models import ApiSubscriptionKey
from policy_platform.infrastructure.persistence.audit import record_audit_event
from policy_platform.infrastructure.persistence.db import get_session
from policy_platform.infrastructure.persistence.subscription_keys import (
    generate_key,
    list_keys,
    revoke_key,
)
from policy_platform.infrastructure.settings import get_settings

router = APIRouter(prefix="/api/integration", tags=["integration"])

SUBSCRIPTION_KEY_ISSUED = "api_subscription_key.issued"
SUBSCRIPTION_KEY_REVOKED = "api_subscription_key.revoked"


class GenerateKeyRequest(BaseModel):
    #: Required, and required to be non-blank. The key itself is unrecoverable
    #: after this call, so the label is the only handle an administrator has for
    #: deciding which row to revoke later.
    label: str = Field(min_length=1, max_length=200)


def _require_local() -> None:
    """Refuse the whole surface unless this deployment owns its own keys.

    404 rather than 403. A deployment behind a gateway does not have this
    feature, and saying "forbidden" would assert that the feature exists and
    that the caller lacks permission — which is a different, and false,
    statement. It also matches what the caller would see if the router were not
    mounted at all, so the API tells the same story as the menu.
    """

    if not get_settings().local:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "integration_keys_not_available",
                "message": (
                    "This deployment does not manage its own subscription keys. They are "
                    "owned by the API gateway in front of it."
                ),
            },
        )


def _to_response(record: ApiSubscriptionKey) -> dict:
    """List shape. Contains no part of the key, because no part of it is stored."""

    return {
        "id": str(record.id),
        "label": record.label,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "created_by": record.created_by,
        "revoked_at": record.revoked_at.isoformat() if record.revoked_at else None,
        "revoked_by": record.revoked_by,
        "last_used_at": record.last_used_at.isoformat() if record.last_used_at else None,
        "active": record.revoked_at is None,
    }


@router.get("/capability")
async def integration_capability() -> dict:
    """Whether this deployment issues its own keys.

    Exists so the admin app can hide the surface rather than render a page that
    every call would then refuse. It is deliberately the *only* endpoint here
    that does not call `_require_local` — a probe that refuses when the answer
    is "no" cannot communicate "no".

    It reports one boolean about deployment shape and nothing else: no key, no
    count, no configuration. That is why it is safe at READ.
    """

    return {"manages_subscription_keys": get_settings().local}


@router.get("/keys")
async def list_subscription_keys(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Every issued key, newest first, revoked ones included.

    Revoked keys stay in the list because "when did this stop working?" is the
    question an administrator asks after an integration fails, and a row that
    vanished on revocation answers it with silence.
    """

    _require_local()
    records = await list_keys(session)
    return {"keys": [_to_response(record) for record in records]}


@router.post("/keys", status_code=201)
async def create_subscription_key(
    payload: GenerateKeyRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Issue a key. **The plaintext is in this response and nowhere else.**

    It is not stored, not logged, and not written into the audit record — the
    audit entry names the label and the row id, which is enough to say what
    happened without the trail itself becoming a place credentials are kept.
    `GET /api/audit-events` is readable by any viewer, so anything placed in
    that body is published to every viewer.

    The key and its audit record commit together. A key that exists with no
    trail, and a trail describing a key that was never created, are both worse
    than the call failing.

    Issuing a key never invalidates an existing one, including the configured
    environment key. Overlap is the point: rotation is issue, migrate, revoke.
    """

    _require_local()
    try:
        record, plaintext = await generate_key(
            session,
            label=payload.label,
            created_by=principal.identity,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_subscription_key_request", "message": str(exc)},
        ) from exc

    await session.flush()
    record_audit_event(
        session,
        event_type=SUBSCRIPTION_KEY_ISSUED,
        entity_type="api_subscription_key",
        entity_id=record.id,
        actor=principal.identity,
        policy_set_key=None,
        details={"label": record.label},
    )
    await session.commit()

    response = _to_response(record)
    # The one moment this value exists outside the caller's own storage. It is
    # named `key` rather than folded into the record shape so that a future
    # change to `_to_response` cannot accidentally start returning it from the
    # list endpoint too.
    response["key"] = plaintext
    response["warning"] = (
        "Copy this key now. It is stored only as a hash and cannot be shown again."
    )
    return response


@router.delete("/keys/{key_id}")
async def delete_subscription_key(
    key_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Revoke a key. The row is kept; only its usability ends.

    Deleting the row would break the audit trail that names it, and would
    destroy the record of when the key stopped working — which is the fact
    somebody needs when an integration breaks.
    """

    _require_local()
    record = await revoke_key(session, key_id=key_id, revoked_by=principal.identity)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "subscription_key_not_found", "message": "No such subscription key."},
        )

    record_audit_event(
        session,
        event_type=SUBSCRIPTION_KEY_REVOKED,
        entity_type="api_subscription_key",
        entity_id=record.id,
        actor=principal.identity,
        policy_set_key=None,
        details={"label": record.label},
    )
    await session.commit()
    return _to_response(record)
