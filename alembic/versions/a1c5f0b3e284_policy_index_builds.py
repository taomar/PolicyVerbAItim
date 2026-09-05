"""policy index builds: an attempt's progress, its history entry, and the one build slot

WHY A TABLE AND NOT ANOTHER COLUMN ON `policy_index_states`

`policy_index_states` holds one row per project and every attempt overwrites it.
That is the right shape for the question it answers — "what does this project's
index look like now" — and it is structurally incapable of answering "what has
happened to this index". A publisher whose build failed, was retried and failed
again has one row saying `failed`, indistinguishable from a first failure.

Widening that row cannot fix it. Any number of attempt columns still describes
one attempt, and the moment a second is needed the row becomes a fixed-length
queue maintained by hand. Attempts are appended here instead, and the latest-
state row keeps doing the single-read job the retrieval side and the project page
depend on. Both are written from one place, so they describe the same attempt.

WHY THE UNIQUE CONSTRAINT ON `active_slot` IS THE INTERESTING PART

A policy-index build renders and embeds a whole corpus through rate-limited model
endpoints and then rewrites an entire search index. Two running at once compete
for the same quota, and two on one project race each other's manifest writes —
which is the one state the build's own ordering argument cannot recover from,
because each would see the other's half-written corpus as stale and sweep it.

The obvious guard is a module-level boolean, and it is wrong here for a reason
that is a property of the deployment rather than of taste: the API runs behind
more than one replica, so a flag in one process says nothing about what another
is doing, and calling such a flag "global" would be a claim rather than a
mechanism.

`active_slot` holds one constant value while a build runs and NULL once it has
ended. Under a UNIQUE constraint, NULLs are distinct — in PostgreSQL and in
SQLite alike — so every finished row coexists happily while at most one row in
the whole table may hold the live value. Acquiring the slot is an INSERT;
refusing a concurrent build is the database rejecting it. That decision is made
in one place for every replica, every process and every worker, and no amount of
application code can disagree with it.

Releasing is setting the column to NULL in the same statement that writes the
terminal status, so a build cannot finish without releasing the slot, and cannot
release it without finishing.

WHY `deferred` IS IN THIS TABLE'S STATUSES AND NOT IN THE OTHER'S

A publish's index build is best-effort: the publish is already committed by the
time it runs, and it must not fail because the slot was busy. That attempt never
ran, which is a different fact from one that ran and failed — the repair is to
wait and retry rather than to investigate. This table can say so.

`policy_index_states.status` deliberately keeps its existing three-value check
constraint. What that row reports is whether the index can be trusted, and on
that question "never ran" and "failed" say exactly the same thing; widening it
would add a third answer to a two-answer question and every existing reader of
that column would have to learn a value that changes nothing for it.

WHAT THIS TABLE MAY NEVER HOLD

Stage keys, counts, timestamps, an actor, and a bounded failure description.
There is deliberately no column here that could carry rendered text, source text,
a service reply body, a prompt or a credential — the rows are served to the
browser and copied into logs.

WHAT DOWNGRADE COSTS

The build history and the cross-process build slot, and nothing else. No index
document is touched and no corpus is rebuilt: a downgraded database simply
cannot remember what was attempted, and coordinates nothing — which is exactly
where this deployment stood before this revision.

Revision ID: a1c5f0b3e284
Revises: f4b8c2e97d31
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "a1c5f0b3e284"
down_revision = "f4b8c2e97d31"
branch_labels = None
depends_on = None

TABLE = "policy_index_builds"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("operation_id", sa.String(length=64), nullable=False),
        sa.Column(
            "policy_set_id",
            UUID(as_uuid=True),
            sa.ForeignKey("policy_sets.id"),
            nullable=False,
        ),
        sa.Column("policy_set_key", sa.String(length=200), nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("actor", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=True),
        # Every counter is nullable because NULL is a fact this table has to be
        # able to state: "not measured yet", which is not zero.
        sa.Column("projection_count", sa.Integer(), nullable=True),
        sa.Column("policy_unit_count", sa.Integer(), nullable=True),
        sa.Column("rule_unit_count", sa.Integer(), nullable=True),
        sa.Column("rendered_count", sa.Integer(), nullable=True),
        sa.Column("embedded_count", sa.Integer(), nullable=True),
        sa.Column("expected_document_count", sa.Integer(), nullable=True),
        sa.Column("submitted_count", sa.Integer(), nullable=True),
        sa.Column("acknowledged_count", sa.Integer(), nullable=True),
        sa.Column("swept_count", sa.Integer(), nullable=True),
        sa.Column("index_name", sa.String(length=128), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=True),
        sa.Column("document_count", sa.Integer(), nullable=True),
        sa.Column("policy_document_count", sa.Integer(), nullable=True),
        sa.Column("rule_document_count", sa.Integer(), nullable=True),
        sa.Column("projection_profile", sa.String(length=64), nullable=True),
        sa.Column("manifest_state", sa.String(length=20), nullable=True),
        sa.Column("quality_state", sa.String(length=20), nullable=True),
        sa.Column("quality_profile", sa.String(length=64), nullable=True),
        sa.Column("quality_checked_documents", sa.Integer(), nullable=True),
        sa.Column("quality_structural_findings", sa.Integer(), nullable=True),
        sa.Column("quality_min_similarity", sa.Float(), nullable=True),
        sa.Column("quality_mean_similarity", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_slot", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("active_slot", name="uq_policy_index_builds_active_slot"),
        sa.UniqueConstraint("operation_id", name="uq_policy_index_builds_operation"),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'deferred')",
            name="ck_policy_index_builds_status",
        ),
        sa.CheckConstraint(
            "trigger IN ('publish', 'rebuild')",
            name="ck_policy_index_builds_trigger",
        ),
    )
    op.create_index(
        "ix_policy_index_builds_policy_set_id", TABLE, ["policy_set_id"], unique=False
    )
    # The history read is "this project's attempts, newest first".
    op.create_index(
        "ix_policy_index_builds_set_started", TABLE, ["policy_set_id", "started_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_policy_index_builds_set_started", table_name=TABLE)
    op.drop_index("ix_policy_index_builds_policy_set_id", table_name=TABLE)
    op.drop_table(TABLE)
