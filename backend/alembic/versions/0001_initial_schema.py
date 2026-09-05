"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-09-04 14:19:06.061369+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Initial Phase 1 schema: users, roles, modules, permissions, sessions,
    # password reset/history and audit logs.
    op.create_table('modules',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('icon', sa.String(length=16), nullable=True),
    sa.Column('route', sa.String(length=160), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_core', sa.Boolean(), nullable=False),
    sa.Column('is_implemented', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_modules'))
    )
    op.create_index(op.f('ix_modules_key'), 'modules', ['key'], unique=True)
    op.create_table('roles',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('is_system', sa.Boolean(), nullable=False),
    sa.Column('is_superuser', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_roles'))
    )
    op.create_index(op.f('ix_roles_key'), 'roles', ['key'], unique=True)
    op.create_table('users',
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('first_name', sa.String(length=120), nullable=False),
    sa.Column('last_name', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('must_change_password', sa.Boolean(), nullable=False),
    sa.Column('job_title', sa.String(length=160), nullable=True),
    sa.Column('department', sa.String(length=160), nullable=True),
    sa.Column('phone', sa.String(length=64), nullable=True),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('failed_login_count', sa.Integer(), nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by_id', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_users_created_by_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_status'), 'users', ['status'], unique=False)
    op.create_table('audit_logs',
    sa.Column('actor_user_id', sa.UUID(), nullable=True),
    sa.Column('actor_email', sa.String(length=320), nullable=True),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('success', sa.Boolean(), nullable=False),
    sa.Column('entity_type', sa.String(length=64), nullable=True),
    sa.Column('entity_id', sa.String(length=64), nullable=True),
    sa.Column('ip_address', postgresql.INET(), nullable=True),
    sa.Column('user_agent', sa.Text(), nullable=True),
    sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], name=op.f('fk_audit_logs_actor_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs'))
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_email'), 'audit_logs', ['actor_email'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_user_id'), 'audit_logs', ['actor_user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_id'), 'audit_logs', ['entity_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_type'), 'audit_logs', ['entity_type'], unique=False)
    op.create_table('password_history',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default='now()', nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_password_history_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_password_history'))
    )
    op.create_index(op.f('ix_password_history_user_id'), 'password_history', ['user_id'], unique=False)
    op.create_table('password_reset_tokens',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('requested_ip', postgresql.INET(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_password_reset_tokens_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_password_reset_tokens'))
    )
    op.create_index(op.f('ix_password_reset_tokens_token_hash'), 'password_reset_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)
    op.create_table('role_module_permissions',
    sa.Column('role_id', sa.UUID(), nullable=False),
    sa.Column('module_id', sa.UUID(), nullable=False),
    sa.Column('access_level', sa.String(length=32), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['module_id'], ['modules.id'], name=op.f('fk_role_module_permissions_module_id_modules'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_role_module_permissions_role_id_roles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_role_module_permissions')),
    sa.UniqueConstraint('role_id', 'module_id', name='uq_role_module_permissions_role_id_module_id')
    )
    op.create_index(op.f('ix_role_module_permissions_module_id'), 'role_module_permissions', ['module_id'], unique=False)
    op.create_index(op.f('ix_role_module_permissions_role_id'), 'role_module_permissions', ['role_id'], unique=False)
    op.create_table('sessions',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_reason', sa.String(length=64), nullable=True),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rotated_from_id', sa.UUID(), nullable=True),
    sa.Column('ip_address', postgresql.INET(), nullable=True),
    sa.Column('user_agent', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['rotated_from_id'], ['sessions.id'], name=op.f('fk_sessions_rotated_from_id_sessions'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sessions'))
    )
    op.create_index(op.f('ix_sessions_token_hash'), 'sessions', ['token_hash'], unique=True)
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)
    op.create_table('user_roles',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role_id', sa.UUID(), nullable=False),
    sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('assigned_by_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['assigned_by_id'], ['users.id'], name=op.f('fk_user_roles_assigned_by_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_user_roles_role_id_roles'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_roles_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_roles')),
    sa.UniqueConstraint('user_id', 'role_id', name='uq_user_roles_user_id_role_id')
    )
    op.create_index(op.f('ix_user_roles_role_id'), 'user_roles', ['role_id'], unique=False)
    op.create_index(op.f('ix_user_roles_user_id'), 'user_roles', ['user_id'], unique=False)
    


def downgrade() -> None:
    # Initial Phase 1 schema: users, roles, modules, permissions, sessions,
    # password reset/history and audit logs.
    op.drop_index(op.f('ix_user_roles_user_id'), table_name='user_roles')
    op.drop_index(op.f('ix_user_roles_role_id'), table_name='user_roles')
    op.drop_table('user_roles')
    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions')
    op.drop_index(op.f('ix_sessions_token_hash'), table_name='sessions')
    op.drop_table('sessions')
    op.drop_index(op.f('ix_role_module_permissions_role_id'), table_name='role_module_permissions')
    op.drop_index(op.f('ix_role_module_permissions_module_id'), table_name='role_module_permissions')
    op.drop_table('role_module_permissions')
    op.drop_index(op.f('ix_password_reset_tokens_user_id'), table_name='password_reset_tokens')
    op.drop_index(op.f('ix_password_reset_tokens_token_hash'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_index(op.f('ix_password_history_user_id'), table_name='password_history')
    op.drop_table('password_history')
    op.drop_index(op.f('ix_audit_logs_entity_type'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_entity_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_created_at'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_actor_user_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_actor_email'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_index(op.f('ix_users_status'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_roles_key'), table_name='roles')
    op.drop_table('roles')
    op.drop_index(op.f('ix_modules_key'), table_name='modules')
    op.drop_table('modules')
    
