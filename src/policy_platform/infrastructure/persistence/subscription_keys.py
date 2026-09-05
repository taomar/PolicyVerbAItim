"""Issuing, verifying and revoking API subscription keys.

The store behind the Integration screen. Everything that touches a key's
plaintext happens here and nowhere else: the module generates a key, hashes it,
and hands the plaintext back to exactly one caller — the endpoint that created
it. Nothing here logs a key, and nothing here can return one after generation,
because after `generate` nothing holds it.

WHY VERIFICATION LIVES HERE AND NOT IN `authz.py`

`authz.py` is the API layer and must not import infrastructure directly for its
own reasons, but more usefully: hashing, lookup and the "is it revoked?"
question are one decision, and splitting them would let a caller check the hash
without checking revocation. Keeping them in one function means a caller cannot
accidentally accept a revoked key by asking the wrong question.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from policy_platform.domain.models import ApiSubscriptionKey

#: Bytes of entropy per key. 32 bytes is 256 bits, rendered by
#: `token_urlsafe` as 43 base64url characters. Chosen so the key is not
#: guessable rather than so it is short: at this size an online attacker gets
#: nowhere and an offline one has nothing to work with, which is what lets the
#: stored digest be a plain unsalted SHA-256.
_KEY_BYTES = 32


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_key(plaintext: str) -> str:
    """The stored representation of a key.

    One function so the generate path and the verify path cannot disagree about
    encoding or digest — if they did, every key would be issued successfully and
    then fail to authenticate, which is a confusing way to be broken.
    """

    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


async def generate_key(
    session: AsyncSession,
    *,
    label: str,
    created_by: str,
) -> tuple[ApiSubscriptionKey, str]:
    """Mint a key, store its hash, and return the row **and the plaintext**.

    The plaintext is returned rather than stored, and this is the only moment it
    exists anywhere in the system. The caller is responsible for putting it in
    exactly one response body and then dropping it: it must not be logged, must
    not be placed in an audit record, and must not be held for a second use.

    The row is added to the caller's transaction but not committed here, so key
    creation and its audit record commit together or not at all. A key that
    exists with no audit trail, or an audit record for a key that was never
    created, are both worse than the operation simply failing.
    """

    cleaned = label.strip()
    if not cleaned:
        # A key whose only human-readable handle is blank cannot be told apart
        # from any other in the list, and the plaintext is unrecoverable — so
        # an admin would have no way to decide which row to revoke.
        raise ValueError("A subscription key needs a label.")

    actor = created_by.strip()
    if not actor:
        raise ValueError("A subscription key must record who created it.")

    plaintext = secrets.token_urlsafe(_KEY_BYTES)
    record = ApiSubscriptionKey(
        label=cleaned,
        key_hash=hash_key(plaintext),
        created_by=actor,
    )
    session.add(record)
    return record, plaintext


async def verify_key(session: AsyncSession, presented: str) -> ApiSubscriptionKey | None:
    """The active key matching what was presented, or None.

    Returns None for "no such key" and for "revoked" alike, on purpose: the
    caller's refusal must not distinguish them, because a response that says
    *revoked* rather than *invalid* confirms to an attacker that they hold a
    real key and only need an older one.

    `last_used_at` is stamped on success and left to the caller's transaction to
    commit. It is deliberately not a usage log — no path, no timestamp series,
    no request detail — only enough for an admin to tell a key that is in use
    from one that has been abandoned, before revoking it.
    """

    candidate = presented.strip()
    if not candidate:
        return None

    result = await session.execute(
        select(ApiSubscriptionKey).where(ApiSubscriptionKey.key_hash == hash_key(candidate))
    )
    record = result.scalar_one_or_none()
    if record is None or record.revoked_at is not None:
        return None

    record.last_used_at = _utcnow()
    return record


async def list_keys(session: AsyncSession) -> list[ApiSubscriptionKey]:
    """Every key, newest first, revoked ones included.

    Revoked keys are listed rather than hidden because the screen is the only
    record an operator sees, and "this key was revoked on that date" is the
    question they ask after an integration stops working.
    """

    result = await session.execute(
        select(ApiSubscriptionKey).order_by(ApiSubscriptionKey.created_at.desc())
    )
    return list(result.scalars())


async def revoke_key(
    session: AsyncSession,
    *,
    key_id: uuid.UUID,
    revoked_by: str,
) -> ApiSubscriptionKey | None:
    """Mark a key unusable. Returns None if there is no such key.

    Revoking an already-revoked key leaves the original revocation time and
    actor intact and reports success. The caller asked for the key to be
    unusable and it is; overwriting the record would destroy the more useful
    fact of when it *first* stopped working.
    """

    actor = revoked_by.strip()
    if not actor:
        raise ValueError("Revoking a subscription key must record who did it.")

    result = await session.execute(
        select(ApiSubscriptionKey).where(ApiSubscriptionKey.id == key_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None

    if record.revoked_at is None:
        record.revoked_at = _utcnow()
        record.revoked_by = actor
    return record
