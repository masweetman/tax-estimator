"""add totp fields to user

Revision ID: 58b5744ca314
Revises: 5e666c9bc2b4
Create Date: 2026-04-05 16:22:57.844658

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '58b5744ca314'
down_revision = '5e666c9bc2b4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('totp_secret', sa.String(64), nullable=True))
    op.add_column('user', sa.Column('totp_enabled', sa.Boolean(), nullable=False,
                                    server_default=sa.false()))


def downgrade():
    op.drop_column('user', 'totp_enabled')
    op.drop_column('user', 'totp_secret')
