"""Initial configuration records, monthly ledger, and daily usage rollups."""

from alembic import op
from tollgate.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind())


def downgrade():
    # Data loss requires an explicit maintenance decision, never an automatic downgrade.
    raise RuntimeError("Downgrade would destroy the ledger. Restore a tested backup instead.")
