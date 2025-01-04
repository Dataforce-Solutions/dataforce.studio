"""create users table

Revision ID: 001
Revises:
Create Date: 2024-12-29 13:40:29.808234

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("disabled", sa.Boolean(), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column(
            "auth_method",
            sa.Enum("EMAIL", "GOOGLE", name="authprovider"),
            nullable=False,
        ),
        sa.Column("photo", sa.String(), nullable=True),
        sa.Column("hashed_password", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("email"),
        sa.UniqueConstraint("email"),
    )


def downgrade() -> None:
    op.drop_table("users")
