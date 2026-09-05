"""Retire the GUEST access level in favour of READ_ONLY

Guest access is now expressed through ordinary effective permissions -- the
Guest *role* holding READ_ONLY grants -- rather than through a distinct access
level. Role configuration therefore offers the three levels operators actually
reason about: No access / Read only / Complete.

Both levels already permitted exactly the same action (VIEW), so this is a
representation change, not a change in what anyone can do.

The ``GUEST`` enum value is retained in application code so that any row written
before this migration still loads and ranks correctly.

Revision ID: 0002_guest_access
Revises: 0001_initial
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_guest_access"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Data-only migration. Non-destructive: GUEST and READ_ONLY are equivalent
    # in the permitted-action table, so no grant is widened or narrowed.
    op.execute(
        sa.text(
            "UPDATE role_module_permissions "
            "SET access_level = 'READ_ONLY' "
            "WHERE access_level = 'GUEST'"
        )
    )


def downgrade() -> None:
    # Deliberately a no-op: which rows were originally GUEST is not recorded,
    # and converting every READ_ONLY row back would wrongly demote grants that
    # were always READ_ONLY. The application still understands GUEST, so a
    # downgraded schema keeps working.
    pass
