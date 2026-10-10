"""Keep the Energy quota fact fully supported by each evidence alternative.

Revision ID: f37d62d8a19b
Revises: 8e8bc5524150
"""
from alembic import op
import sqlalchemy as sa

revision = "f37d62d8a19b"
down_revision = "8e8bc5524150"
branch_labels = None
depends_on = None

OLD = "Energy has no free quota; an account can stake, receive delegated resources, or use the TRX-burn fallback."
NEW = "Energy has no free quota."


def replace(old, new):
    op.get_bind().execute(sa.text(
        "UPDATE assertions SET text = :new WHERE id = 'FACT-05' AND text = :old"
    ), {"old": old, "new": new})


def upgrade():
    replace(OLD, NEW)


def downgrade():
    replace(NEW, OLD)
