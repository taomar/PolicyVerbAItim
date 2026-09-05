"""api subscription keys: a store, so a key can be issued and revoked

WHAT THIS CHANGES ABOUT A DECISION ALREADY RECORDED

`settings.py` has said, since subscription-key authentication was added, that
the mechanism is "deliberately *one* key, not a keyring", and gave a reason:

    Rotation is: change the value, restart the API. There is no overlap window
    and no revocation list, and inventing either without a store to hold them
    would be a claim rather than a feature.

This revision supplies the store that sentence named as missing. The earlier
decision is therefore satisfied rather than contradicted — the precondition it
set out has been met — and the comment there is updated to say so rather than
quietly dropped.

WHAT IS STORED

A SHA-256 hash of each key, never the key. The plaintext is returned once, in
the response to the call that generated it, and is not recoverable afterwards.
See `ApiSubscriptionKey` for why an unsalted digest is the right choice for a
256-bit machine-generated secret and why a salted KDF would be a denial-of-
service amplifier on this particular code path.

There is deliberately no column here that could hold the key, a prefix of it, or
any fragment: `GET /api/audit-events` is viewer-readable, and a hint column
would eventually be copied into an audit body by someone trying to make a list
screen more helpful.

WHAT IS NOT BACKFILLED

Nothing. `POLICY_SUBSCRIPTION_KEY` stays exactly where it is and keeps working
unchanged; keys issued through this table are additional. Importing the
configured value as a row was considered and rejected — it would put a hash of a
value that also lives in the environment into the database, and a later change
to the environment would then silently do nothing.

WHY THE UNIQUE INDEX IS ON THE HASH

Verification is a single indexed equality on `key_hash`, which is what keeps the
cost independent of how many keys exist. Uniqueness also means the same key
cannot be recorded twice, which would otherwise make revocation ambiguous.

Revision ID: f4b8c2e97d31
Revises: e3a7c9d15b82
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "f4b8c2e97d31"
down_revision = "e3a7c9d15b82"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_subscription_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(length=200), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_api_subscription_keys_key_hash",
        "api_subscription_keys",
        ["key_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_api_subscription_keys_key_hash", table_name="api_subscription_keys")
    op.drop_table("api_subscription_keys")
