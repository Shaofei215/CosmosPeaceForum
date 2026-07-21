"""创建当前角色管理服务初始数据库结构。

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-21

本文件由 Alembic 生成，供角色管理后端启动时按版本顺序升级或回退数据库结构。
本基线对应 v1.0.0-beta.1，显式描述当前 SQLModel metadata 中的全部表和索引，
不依赖运行时 ``create_all``。
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa



revision: str = '0001_initial_schema'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建当前 Agent 管理服务运行所需的全部数据库对象。"""

    op.create_table('admin_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('admin_id', sa.Integer(), nullable=False),
    sa.Column('scope', sa.String(length=32), nullable=False),
    sa.Column('client_type', sa.String(length=32), nullable=False),
    sa.Column('refresh_token_hash', sa.String(length=64), nullable=False),
    sa.Column('revoked_at', sa.DateTime(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(), nullable=False),
    sa.Column('user_agent', sa.Text(), nullable=True),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('remember_me', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_sessions_admin_id'), 'admin_sessions', ['admin_id'], unique=False)
    op.create_index(op.f('ix_admin_sessions_client_type'), 'admin_sessions', ['client_type'], unique=False)
    op.create_index(op.f('ix_admin_sessions_expires_at'), 'admin_sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_admin_sessions_refresh_token_hash'), 'admin_sessions', ['refresh_token_hash'], unique=True)
    op.create_index(op.f('ix_admin_sessions_revoked_at'), 'admin_sessions', ['revoked_at'], unique=False)
    op.create_index(op.f('ix_admin_sessions_scope'), 'admin_sessions', ['scope'], unique=False)
    op.create_index(op.f('ix_admin_sessions_session_id'), 'admin_sessions', ['session_id'], unique=True)
    op.create_table('admin_users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=50), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('permissions', sa.Text(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_super_admin', sa.Boolean(), nullable=False),
    sa.Column('must_change_credentials', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('last_login', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_users_username'), 'admin_users', ['username'], unique=True)
    op.create_table('chunk_model_configs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('api_key', sa.String(length=500), nullable=False),
    sa.Column('base_url', sa.String(length=500), nullable=False),
    sa.Column('model_name', sa.String(length=100), nullable=False),
    sa.Column('temperature', sa.Float(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('max_token', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chunk_model_configs_name'), 'chunk_model_configs', ['name'], unique=True)
    op.create_table('embedding_configs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('base_url', sa.String(length=500), nullable=False),
    sa.Column('api_key', sa.String(length=500), nullable=False),
    sa.Column('model_name', sa.String(length=100), nullable=False),
    sa.Column('dimension', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('model_configs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('api_key', sa.String(length=500), nullable=False),
    sa.Column('base_url', sa.String(length=500), nullable=False),
    sa.Column('model_name', sa.String(length=100), nullable=False),
    sa.Column('temperature', sa.Float(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('max_token', sa.Integer(), nullable=False),
    sa.Column('color', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_model_configs_name'), 'model_configs', ['name'], unique=True)
    op.create_table('operation_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('operator_id', sa.Integer(), nullable=True),
    sa.Column('operator_username', sa.String(length=50), nullable=True),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('target_type', sa.String(length=50), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=True),
    sa.Column('details', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_operation_logs_operator_id'), 'operation_logs', ['operator_id'], unique=False)
    op.create_table('prompt_configs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('default_value', sa.Text(), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prompt_configs_key'), 'prompt_configs', ['key'], unique=True)
    op.create_table('system_configs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('value', sa.String(length=1000), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_system_configs_key'), 'system_configs', ['key'], unique=True)
    op.create_table('agent_configs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('username', sa.String(length=100), nullable=False),
    sa.Column('monthly_logins', sa.Integer(), nullable=False),
    sa.Column('personal_signature', sa.String(length=500), nullable=False),
    sa.Column('personality_prompt', sa.String(length=4000), nullable=False),
    sa.Column('knows_ids', sa.String(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('model_config_id', sa.Integer(), nullable=True),
    sa.Column('social_platform_user_id', sa.Integer(), nullable=True),
    sa.Column('last_login_at', sa.DateTime(), nullable=True),
    sa.Column('last_login_timestamp', sa.Float(), nullable=True),
    sa.Column('total_login_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['model_config_id'], ['model_configs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_configs_username'), 'agent_configs', ['username'], unique=True)
    op.create_table('scheduler_time_state',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scaled_timestamp', sa.Float(), nullable=False),
    sa.Column('real_timestamp', sa.Float(), nullable=False),
    sa.Column('scale', sa.Float(), nullable=False),
    sa.Column('offset_seconds', sa.Integer(), nullable=False),
    sa.Column('paused', sa.Boolean(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """按外键依赖的逆序删除当前 Agent 管理服务数据库对象。"""

    op.drop_table('scheduler_time_state')
    op.drop_index(op.f('ix_agent_configs_username'), table_name='agent_configs')
    op.drop_table('agent_configs')
    op.drop_index(op.f('ix_system_configs_key'), table_name='system_configs')
    op.drop_table('system_configs')
    op.drop_index(op.f('ix_prompt_configs_key'), table_name='prompt_configs')
    op.drop_table('prompt_configs')
    op.drop_index(op.f('ix_operation_logs_operator_id'), table_name='operation_logs')
    op.drop_table('operation_logs')
    op.drop_index(op.f('ix_model_configs_name'), table_name='model_configs')
    op.drop_table('model_configs')
    op.drop_table('embedding_configs')
    op.drop_index(op.f('ix_chunk_model_configs_name'), table_name='chunk_model_configs')
    op.drop_table('chunk_model_configs')
    op.drop_index(op.f('ix_admin_users_username'), table_name='admin_users')
    op.drop_table('admin_users')
    op.drop_index(op.f('ix_admin_sessions_session_id'), table_name='admin_sessions')
    op.drop_index(op.f('ix_admin_sessions_scope'), table_name='admin_sessions')
    op.drop_index(op.f('ix_admin_sessions_revoked_at'), table_name='admin_sessions')
    op.drop_index(op.f('ix_admin_sessions_refresh_token_hash'), table_name='admin_sessions')
    op.drop_index(op.f('ix_admin_sessions_expires_at'), table_name='admin_sessions')
    op.drop_index(op.f('ix_admin_sessions_client_type'), table_name='admin_sessions')
    op.drop_index(op.f('ix_admin_sessions_admin_id'), table_name='admin_sessions')
    op.drop_table('admin_sessions')
