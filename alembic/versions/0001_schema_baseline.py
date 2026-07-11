"""Establish the versioned PaperGazer schema baseline.

Revision ID: 0001_schema_baseline
Revises: None
"""

from collections.abc import Sequence

from alembic import op
from papergazer.store.db import Base

revision: str = "0001_schema_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing installations are normalized by the legacy bridge before this
    # revision is applied.  New installations create the exact ORM metadata.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # The baseline is deliberately non-destructive: dropping the complete
    # literature database is never a safe automatic downgrade.
    pass
