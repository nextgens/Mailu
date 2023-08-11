"""create the totp table

Revision ID: ceb8d814a41c
Revises: 0ba45693748d
Create Date: 2023-08-11 15:40:40.967308

"""

# revision identifiers, used by Alembic.
revision = 'ceb8d814a41c'
down_revision = '0ba45693748d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('totp',
    sa.Column('created_at', sa.Date(), nullable=False),
    sa.Column('updated_at', sa.Date(), nullable=True),
    sa.Column('comment', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_email', sa.String(length=255), nullable=False),
    sa.Column('b32secret', sa.String(length=16), nullable=False),
    sa.ForeignKeyConstraint(['user_email'], ['user.email'], name=op.f('totp_user_email_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('totp_pkey'))
    )


def downgrade():
    op.drop_table('totp')
