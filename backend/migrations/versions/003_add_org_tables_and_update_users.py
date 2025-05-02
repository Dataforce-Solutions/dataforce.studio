"""Add org tables and update users

Revision ID: 003
Revises: 002
Create Date: 2025-05-02 18:30:02.103035

"""

import datetime
import uuid
from collections.abc import Sequence
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("id", sa.Uuid(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )
    op.add_column(
        "users", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
    )

    now = datetime.datetime.now(datetime.UTC)
    conn = op.get_bind()

    users = conn.execute(sa.text("SELECT email FROM users")).fetchall()

    for (email,) in users:
        conn.execute(
            sa.text("UPDATE users SET id = :id, created_at = :now, updated_at = :now WHERE email = :email"),
            {"id": str(uuid.uuid4()), "now": now, "email": email},
        )


    op.drop_constraint("users_pkey", "users", type_="primary")
    op.create_primary_key("users_pkey", "users", ["id"])
    op.alter_column("users", "created_at", nullable=False)
    op.alter_column("users", "updated_at", nullable=False)



    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("logo", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
        sa.UniqueConstraint("id", name="uq_organizations_id"),
    )
    op.create_table(
        "organization_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("OWNER", "ADMIN", "MEMBER", name="orgrole", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
            name="fk_org_members_org",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_org_members_user"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organization_members"),
        sa.UniqueConstraint("id", name="uq_organization_members_id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )
    op.create_table('organizations',
                    sa.Column('id', sa.Uuid(), nullable=False),
                    sa.Column('name', sa.String(), nullable=False),
                    sa.Column('logo', sa.String(), nullable=True),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('id')
                    )
    op.create_table('organization_members',
                    sa.Column('id', sa.Uuid(), nullable=False),
                    sa.Column('user_id', sa.UUID(), nullable=False),
                    sa.Column('organization_id', sa.UUID(), nullable=False),
                    sa.Column('role', sa.Enum('OWNER', 'ADMIN', 'MEMBER', name='orgrole'), nullable=False),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
                    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('id'),
                    sa.UniqueConstraint('organization_id', 'user_id', name='org_member')
                    )



    results = conn.execute(sa.text("SELECT id, email, full_name FROM users")).fetchall()

    for id, email, full_name in results:
        org_id = uuid.uuid4()
        org_name = f"{full_name or email.split('@')[0]}'s organization"

        conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, created_at, updated_at) VALUES (:id, :name, :created_at, :updated_at)"
            ),
            {
                "id": str(org_id),
                "name": org_name,
                "created_at": now,
                "updated_at": now,
            },
        )

        conn.execute(
            sa.text(
                """INSERT INTO organization_members (id, user_id, organization_id, role, created_at, updated_at)
                   VALUES (:id, :user_id, :organization_id, :role, :created_at, :updated_at)"""
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": id,
                "organization_id": str(org_id),
                "role": "OWNER",
                "created_at": now,
                "updated_at": now,
            },
        )


def downgrade() -> None:
    op.drop_constraint(None, 'users', type_='unique')
    op.drop_column('users', 'updated_at')
    op.drop_column('users', 'created_at')
    op.drop_column('users', 'id')
    op.drop_table('organization_members')
    op.drop_table('organizations')
