"""baseline: empty starting point; the tables come in T-017 and T-018

Revision ID: 7d1f9ad98a61
Revises:
Create Date: 2026-11-14 13:57:08.841802

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "7d1f9ad98a61"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
