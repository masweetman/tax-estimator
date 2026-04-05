"""Add TOTP 2FA columns to user table.

Revision ID: a3f81c2d9e47
Revises: 5e666c9bc2b4
Create Date: 2026-04-05

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a3f81c2d9e47"
down_revision = "5e666c9bc2b4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user", sa.Column("totp_secret", sa.String(64), nullable=True))
    op.add_column(
        "user",
        sa.Column(
            "totp_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade():
    op.drop_column("user", "totp_enabled")
    op.drop_column("user", "totp_secret")
