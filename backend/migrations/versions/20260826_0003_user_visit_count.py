"""Add successful-login visit counters to users."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260826_0003"
down_revision: Union[str, None] = "20260826_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("visit_count", sa.Integer(), server_default="0", nullable=False),
    )
    # Existing auth sessions each represent one historical successful login.
    op.execute(
        """
        UPDATE users
        SET visit_count = (
            SELECT count(*)
            FROM auth_sessions
            WHERE auth_sessions.user_id = users.id
        )
        """
    )


def downgrade() -> None:
    op.drop_column("users", "visit_count")
