"""Add remaining_amount column to loans

Revision ID: 040c1306aa57
Revises: fcdb448fbd8b
Create Date: 2025-09-20 00:56:47.894020

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '040c1306aa57'
down_revision = 'fcdb448fbd8b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("loans", schema=None) as batch_op:
        # Step 1: add as nullable
        batch_op.add_column(sa.Column("remaining_amount", sa.Numeric(12, 2), nullable=True))

    # Step 2: initialize data
    op.execute("UPDATE loans SET remaining_amount = approved_amount")

    # Step 3: make column non-nullable
    with op.batch_alter_table("loans", schema=None) as batch_op:
        batch_op.alter_column("remaining_amount", nullable=False)


def downgrade():
    with op.batch_alter_table("loans", schema=None) as batch_op:
        batch_op.drop_column("remaining_amount")
