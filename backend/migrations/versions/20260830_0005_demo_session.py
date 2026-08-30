"""Add demo sessions table for judge demo mode (shared session)."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260830_0005"
down_revision: Union[str, None] = "20260826_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "demo_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("encrypted_token", sa.Text(), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("demo_sessions")
