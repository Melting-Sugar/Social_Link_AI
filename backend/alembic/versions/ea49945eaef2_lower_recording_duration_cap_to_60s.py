"""lower recording duration cap to 60s

Revision ID: ea49945eaef2
Revises: cc2500859bb7
Create Date: 2026-08-05 09:01:47.551695

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea49945eaef2'
down_revision: Union[str, Sequence[str], None] = 'cc2500859bb7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("ck_recording_duration_max", "recordings", type_="check")
    op.create_check_constraint("ck_recording_duration_max", "recordings", "duration_sec <= 60")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_recording_duration_max", "recordings", type_="check")
    op.create_check_constraint("ck_recording_duration_max", "recordings", "duration_sec <= 1800")
