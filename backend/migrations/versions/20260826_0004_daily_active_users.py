"""Change user visit counts to distinct daily active days."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260826_0004"
down_revision: Union[str, None] = "20260826_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_visit_on", sa.Date(), nullable=True))
    op.create_index("ix_users_last_visit_on", "users", ["last_visit_on"])
    op.execute(
        """
        UPDATE users
        SET
            visit_count = (
                SELECT count(DISTINCT (created_at AT TIME ZONE 'Asia/Shanghai')::date)
                FROM auth_sessions
                WHERE auth_sessions.user_id = users.id
            ),
            last_visit_on = (
                SELECT max((created_at AT TIME ZONE 'Asia/Shanghai')::date)
                FROM auth_sessions
                WHERE auth_sessions.user_id = users.id
            )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_users_last_visit_on", table_name="users")
    op.drop_column("users", "last_visit_on")
