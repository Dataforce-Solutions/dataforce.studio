"""Add org tables and migrate existing users

Revision ID: 003
Revises: 002
Create Date: 2025-05-01 20:04:21.237763

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import uuid
import datetime


revision: str = '003'
down_revision: str | None = '002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('organizations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('logo', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id')
    )
    op.create_table('organization_members',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user', sa.String(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.Enum('OWNER', 'ADMIN', 'MEMBER', name='orgrole'), nullable=False),
    sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user'], ['users.email'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id'),
    sa.UniqueConstraint('organization_id', 'user', name='org_member')
    )
    op.add_column('users', sa.Column('created_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(None, 'users', ['email'])


    now = datetime.datetime.now(datetime.UTC)

    op.execute(sa.text("UPDATE users SET created_at = :now").bindparams(now=now))
    op.alter_column("users", "created_at", nullable=False)
    op.execute(sa.text("UPDATE users SET updated_at = :now").bindparams(now=now))
    op.alter_column("users", "updated_at", nullable=False)

    conn = op.get_bind()
    results = conn.execute(sa.text("SELECT email, full_name FROM users")).fetchall()

    for email, full_name in results:
        org_id = uuid.uuid4()
        org_name = f"{full_name or email.split('@')[0]}'s organization"

        conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, created_at) VALUES (:id, :name, :created_at)"
            ),
            {"id": str(org_id), "name": org_name, "created_at": now},
        )

        conn.execute(
            sa.text(
                """INSERT INTO organization_members (id, "user", organization_id, role, joined_at)
                   VALUES (:id, :user, :organization_id, :role, :joined_at)"""
            ),
            {
                "id": str(uuid.uuid4()),
                "user": email,
                "organization_id": str(org_id),
                "role": "OWNER",
                "joined_at": now,
            },
        )


def downgrade() -> None:
    op.drop_constraint(None, 'users', type_='unique')
    op.drop_column('users', 'updated_at')
    op.drop_column('users', 'created_at')
    op.drop_table('organization_members')
    op.drop_table('organizations')
