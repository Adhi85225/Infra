"""Task updates module

Adds the ``tasks`` table backing the Task Updates page and the per-service task
views.

Case numbers, work-order numbers and Jira keys share a single generic
``reference_number`` column: they are all just an identifier from whichever
system the work arrived through, and the application never reasons about which.

``status`` and ``service`` are plain strings rather than PostgreSQL enums,
matching how ``users.status`` stores :class:`UserStatus` -- adding an option
then needs no schema change.

Revision ID: 0003_task_updates
Revises: 0002_guest_access
Create Date: 2026-09-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_task_updates"
down_revision: Union[str, None] = "0002_guest_access"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("task_date", sa.Date(), nullable=False),
        sa.Column("reference_number", sa.String(length=120), nullable=True),
        sa.Column("site_name", sa.String(length=160), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("service", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_tasks_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_tasks_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index(op.f("ix_tasks_service"), "tasks", ["service"], unique=False)
    op.create_index(op.f("ix_tasks_status"), "tasks", ["status"], unique=False)
    op.create_index(op.f("ix_tasks_task_date"), "tasks", ["task_date"], unique=False)
    op.create_index(op.f("ix_tasks_user_id"), "tasks", ["user_id"], unique=False)
    # Serves the service pages directly: "this service, this user, newest first".
    op.create_index(
        "ix_tasks_service_user_id_task_date",
        "tasks",
        ["service", "user_id", "task_date"],
        unique=False,
    )

    # Standard users need COMPLETE on TASK_UPDATES to file and edit their own
    # tasks. The module shipped unimplemented with a READ_ONLY default, so that
    # grant has never governed anything and raising it takes nothing away.
    #
    # Scoped to rows that still hold the original default: a deployment where an
    # operator has already chosen NONE or COMPLETE is left exactly as they set
    # it, and the seeder never revisits existing rows.
    op.execute(
        sa.text(
            """
            UPDATE role_module_permissions AS rmp
               SET access_level = 'COMPLETE'
              FROM roles AS r, modules AS m
             WHERE rmp.role_id = r.id
               AND rmp.module_id = m.id
               AND r.key = 'USER'
               AND m.key = 'TASK_UPDATES'
               AND rmp.access_level = 'READ_ONLY'
            """
        )
    )


def downgrade() -> None:
    # Restore the seeded default for the grant raised above, so a downgrade
    # leaves the permission table as this migration found it.
    op.execute(
        sa.text(
            """
            UPDATE role_module_permissions AS rmp
               SET access_level = 'READ_ONLY'
              FROM roles AS r, modules AS m
             WHERE rmp.role_id = r.id
               AND rmp.module_id = m.id
               AND r.key = 'USER'
               AND m.key = 'TASK_UPDATES'
               AND rmp.access_level = 'COMPLETE'
            """
        )
    )
    op.drop_index("ix_tasks_service_user_id_task_date", table_name="tasks")
    op.drop_index(op.f("ix_tasks_user_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_task_date"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_status"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_service"), table_name="tasks")
    op.drop_table("tasks")
