"""Rename the Servers task service to Patch Management

The service value is also the label shown in the UI, so renaming the page
without renaming the value would leave a "Patch Management" page on which every
row's Service column still read "Servers".

Module names (``DAS Onboarding`` -> ``DAS``, ``ILO Inventory`` -> ``ILO``,
``Servers`` -> ``Patch Management``) need no migration: the catalogue is synced
from the registry on every start.

Revision ID: 0004_rename_servers
Revises: 0003_task_updates
Create Date: 2026-09-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_rename_servers"
down_revision: Union[str, None] = "0003_task_updates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE tasks SET service = 'Patch Management' WHERE service = 'Servers'")
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE tasks SET service = 'Servers' WHERE service = 'Patch Management'")
    )
