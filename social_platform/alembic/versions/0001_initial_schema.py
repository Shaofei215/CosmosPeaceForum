"""创建当前公开平台初始数据库结构。

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-03 07:16:14.554927

本基线由当前 SQLAlchemy metadata 自动生成，供全新 SQLite 或 PostgreSQL 数据库
在公开平台启动前通过 ``alembic upgrade head`` 一次性建立完整表、约束和索引。
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa



revision: str = '0001_initial_schema'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建当前公开平台运行所需的全部数据库对象。"""

    op.create_table('content_moderation_llm_settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('llm_base_url', sa.String(length=500), nullable=True),
    sa.Column('llm_model_name', sa.String(length=120), nullable=True),
    sa.Column('llm_api_key', sa.String(length=500), nullable=True),
    sa.Column('prompt_template', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('hot_topic_generations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
    sa.Column('publish_policy', sa.String(length=20), server_default='draft', nullable=False),
    sa.Column('input_snapshot', sa.Text(), nullable=True),
    sa.Column('output_json', sa.Text(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hot_topic_generations_id'), 'hot_topic_generations', ['id'], unique=False)
    op.create_table('hot_topic_settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('agent_enabled', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('agent_interval_minutes', sa.Integer(), server_default='180', nullable=False),
    sa.Column('publish_policy', sa.String(length=20), server_default='draft', nullable=False),
    sa.Column('llm_base_url', sa.String(length=500), nullable=True),
    sa.Column('llm_model_name', sa.String(length=120), nullable=True),
    sa.Column('llm_api_key', sa.String(length=500), nullable=True),
    sa.Column('web_search_enabled', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('tavily_api_key', sa.String(length=500), nullable=True),
    sa.Column('history_limit', sa.Integer(), server_default='3', nullable=False),
    sa.Column('max_llm_rounds', sa.Integer(), server_default='6', nullable=False),
    sa.Column('prompt_template', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('platform_admin_operation_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('operator_id', sa.Integer(), nullable=True),
    sa.Column('operator_username', sa.String(length=50), nullable=True),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('target_type', sa.String(length=50), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=True),
    sa.Column('details', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_platform_admin_operation_logs_action'), 'platform_admin_operation_logs', ['action'], unique=False)
    op.create_index(op.f('ix_platform_admin_operation_logs_created_at'), 'platform_admin_operation_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_platform_admin_operation_logs_id'), 'platform_admin_operation_logs', ['id'], unique=False)
    op.create_index(op.f('ix_platform_admin_operation_logs_operator_id'), 'platform_admin_operation_logs', ['operator_id'], unique=False)
    op.create_index(op.f('ix_platform_admin_operation_logs_target_id'), 'platform_admin_operation_logs', ['target_id'], unique=False)
    op.create_index(op.f('ix_platform_admin_operation_logs_target_type'), 'platform_admin_operation_logs', ['target_type'], unique=False)
    op.create_table('platform_admin_users',
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
    op.create_index(op.f('ix_platform_admin_users_id'), 'platform_admin_users', ['id'], unique=False)
    op.create_index(op.f('ix_platform_admin_users_username'), 'platform_admin_users', ['username'], unique=True)
    op.create_table('topics',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=40), nullable=False),
    sa.Column('post_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('heat_score', sa.Float(), server_default='0', nullable=False),
    sa.Column('last_used_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_topics_heat', 'topics', ['heat_score', 'last_used_at', 'id'], unique=False)
    op.create_index(op.f('ix_topics_id'), 'topics', ['id'], unique=False)
    op.create_index(op.f('ix_topics_name'), 'topics', ['name'], unique=True)
    op.create_table('user_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
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
    op.create_index(op.f('ix_user_sessions_account_id'), 'user_sessions', ['account_id'], unique=False)
    op.create_index('ix_user_sessions_account_scope_client', 'user_sessions', ['account_id', 'scope', 'client_type'], unique=False)
    op.create_index(op.f('ix_user_sessions_client_type'), 'user_sessions', ['client_type'], unique=False)
    op.create_index(op.f('ix_user_sessions_expires_at'), 'user_sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_user_sessions_id'), 'user_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_user_sessions_refresh_token_hash'), 'user_sessions', ['refresh_token_hash'], unique=True)
    op.create_index(op.f('ix_user_sessions_revoked_at'), 'user_sessions', ['revoked_at'], unique=False)
    op.create_index(op.f('ix_user_sessions_scope'), 'user_sessions', ['scope'], unique=False)
    op.create_index(op.f('ix_user_sessions_session_id'), 'user_sessions', ['session_id'], unique=True)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=30), nullable=True),
    sa.Column('bio', sa.String(length=100), nullable=True),
    sa.Column('avatar_url', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('password_hash', sa.String(length=255), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('email_verified', sa.Boolean(), nullable=False),
    sa.Column('email_verified_at', sa.DateTime(), nullable=True),
    sa.Column('following_count', sa.Integer(), nullable=False),
    sa.Column('followers_count', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_table('content_report_escalations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=30), server_default='pending', nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('trigger_content_json', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('reviewed_by_admin_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['reviewed_by_admin_id'], ['platform_admin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_content_report_escalations_user_status', 'content_report_escalations', ['user_id', 'status'], unique=False)
    op.create_index(op.f('ix_content_report_escalations_created_at'), 'content_report_escalations', ['created_at'], unique=False)
    op.create_index(op.f('ix_content_report_escalations_id'), 'content_report_escalations', ['id'], unique=False)
    op.create_index(op.f('ix_content_report_escalations_reviewed_by_admin_id'), 'content_report_escalations', ['reviewed_by_admin_id'], unique=False)
    op.create_index(op.f('ix_content_report_escalations_status'), 'content_report_escalations', ['status'], unique=False)
    op.create_index(op.f('ix_content_report_escalations_user_id'), 'content_report_escalations', ['user_id'], unique=False)
    op.create_table('email_verification_codes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('code', sa.String(length=6), nullable=False),
    sa.Column('purpose', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('used', sa.Boolean(), nullable=False),
    sa.Column('used_at', sa.DateTime(), nullable=True),
    sa.Column('attempt_count', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_email_verification_codes_code'), 'email_verification_codes', ['code'], unique=False)
    op.create_index(op.f('ix_email_verification_codes_email'), 'email_verification_codes', ['email'], unique=False)
    op.create_index(op.f('ix_email_verification_codes_id'), 'email_verification_codes', ['id'], unique=False)
    op.create_index(op.f('ix_email_verification_codes_user_id'), 'email_verification_codes', ['user_id'], unique=False)
    op.create_table('follows',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('follower_id', sa.Integer(), nullable=False),
    sa.Column('following_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('created_by_agent', sa.Boolean(), server_default='0', nullable=False),
    sa.ForeignKeyConstraint(['follower_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['following_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('follower_id', 'following_id', name='uq_follow_pair')
    )
    op.create_index('idx_follow_follower_id', 'follows', ['follower_id'], unique=False)
    op.create_index('idx_follow_following_id', 'follows', ['following_id'], unique=False)
    op.create_index(op.f('ix_follows_id'), 'follows', ['id'], unique=False)
    op.create_table('hot_topics',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=120), nullable=False),
    sa.Column('search_query', sa.String(length=200), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), server_default='manual', nullable=False),
    sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
    sa.Column('rank', sa.Integer(), server_default='1', nullable=False),
    sa.Column('weight', sa.Float(), server_default='0', nullable=False),
    sa.Column('is_pinned', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('generation_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['generation_id'], ['hot_topic_generations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hot_topics_generation_status', 'hot_topics', ['generation_id', 'status'], unique=False)
    op.create_index('idx_hot_topics_public_order', 'hot_topics', ['status', 'rank', 'created_at'], unique=False)
    op.create_index(op.f('ix_hot_topics_generation_id'), 'hot_topics', ['generation_id'], unique=False)
    op.create_index(op.f('ix_hot_topics_id'), 'hot_topics', ['id'], unique=False)
    op.create_table('platform_user_moderations',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('account_banned_at', sa.DateTime(), nullable=True),
    sa.Column('account_current_event_id', sa.Integer(), nullable=True),
    sa.Column('account_ban_reason', sa.Text(), nullable=True),
    sa.Column('publish_banned_until', sa.DateTime(), nullable=True),
    sa.Column('publish_violation_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('publish_permanently_banned', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('publish_current_event_id', sa.Integer(), nullable=True),
    sa.Column('publish_ban_reason', sa.Text(), nullable=True),
    sa.Column('comment_banned_until', sa.DateTime(), nullable=True),
    sa.Column('comment_violation_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('comment_permanently_banned', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('comment_current_event_id', sa.Integer(), nullable=True),
    sa.Column('comment_ban_reason', sa.Text(), nullable=True),
    sa.Column('interaction_banned_until', sa.DateTime(), nullable=True),
    sa.Column('interaction_violation_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('interaction_permanently_banned', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('interaction_current_event_id', sa.Integer(), nullable=True),
    sa.Column('interaction_ban_reason', sa.Text(), nullable=True),
    sa.Column('avatar_banned_until', sa.DateTime(), nullable=True),
    sa.Column('avatar_violation_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('avatar_permanently_banned', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('avatar_current_event_id', sa.Integer(), nullable=True),
    sa.Column('avatar_ban_reason', sa.Text(), nullable=True),
    sa.Column('username_banned_until', sa.DateTime(), nullable=True),
    sa.Column('username_violation_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('username_permanently_banned', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('username_current_event_id', sa.Integer(), nullable=True),
    sa.Column('username_ban_reason', sa.Text(), nullable=True),
    sa.Column('bio_banned_until', sa.DateTime(), nullable=True),
    sa.Column('bio_violation_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('bio_permanently_banned', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('bio_current_event_id', sa.Integer(), nullable=True),
    sa.Column('bio_ban_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('updated_by_admin_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_index(op.f('ix_platform_user_moderations_user_id'), 'platform_user_moderations', ['user_id'], unique=False)
    op.create_table('posts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=True),
    sa.Column('type', sa.String(length=20), server_default='post', nullable=False),
    sa.Column('content', sa.String(length=10000), nullable=False),
    sa.Column('created_by_agent', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('like_count', sa.Integer(), nullable=False),
    sa.Column('comment_count', sa.Integer(), nullable=False),
    sa.Column('repost_count', sa.Integer(), nullable=False),
    sa.Column('repost_source_type', sa.String(length=20), nullable=True),
    sa.Column('repost_source_id', sa.Integer(), nullable=True),
    sa.Column('repost_root_post_id', sa.Integer(), nullable=True),
    sa.Column('repost_chain', sa.Text(), nullable=True),
    sa.Column('heat_score', sa.Float(), server_default='0', nullable=False),
    sa.Column('heat_score_updated_at', sa.DateTime(), nullable=True),
    sa.Column('moderation_status', sa.String(length=20), server_default='active', nullable=False),
    sa.Column('archived_at', sa.DateTime(), nullable=True),
    sa.Column('archived_by_admin_id', sa.Integer(), nullable=True),
    sa.Column('archive_reason', sa.Text(), nullable=True),
    sa.CheckConstraint("type = 'article' OR length(content) <= 1000", name='ck_posts_content_post_length'),
    sa.CheckConstraint('length(content) <= 10000', name='ck_posts_content_article_length'),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['repost_root_post_id'], ['posts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_posts_author_latest', 'posts', ['author_id', 'created_at', 'id'], unique=False)
    op.create_index('idx_posts_heat_latest', 'posts', ['heat_score', 'created_at', 'id'], unique=False)
    op.create_index('idx_posts_latest', 'posts', ['created_at', 'id'], unique=False)
    op.create_index('idx_posts_moderation_status', 'posts', ['moderation_status', 'created_at', 'id'], unique=False)
    op.create_index(op.f('ix_posts_id'), 'posts', ['id'], unique=False)
    op.create_index(op.f('ix_posts_repost_root_post_id'), 'posts', ['repost_root_post_id'], unique=False)
    op.create_table('registration_invitations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.Column('prefix', sa.String(length=16), nullable=False),
    sa.Column('code_suffix', sa.String(length=6), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by_admin_id', sa.Integer(), nullable=True),
    sa.Column('used_by_user_id', sa.Integer(), nullable=True),
    sa.Column('used_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_admin_id'], ['platform_admin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['used_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_registration_invitations_code'), 'registration_invitations', ['code'], unique=True)
    op.create_index(op.f('ix_registration_invitations_created_by_admin_id'), 'registration_invitations', ['created_by_admin_id'], unique=False)
    op.create_index(op.f('ix_registration_invitations_email'), 'registration_invitations', ['email'], unique=True)
    op.create_index(op.f('ix_registration_invitations_id'), 'registration_invitations', ['id'], unique=False)
    op.create_index(op.f('ix_registration_invitations_used_by_user_id'), 'registration_invitations', ['used_by_user_id'], unique=True)
    op.create_table('comments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('root_comment_id', sa.Integer(), nullable=True),
    sa.Column('content', sa.String(length=1000), nullable=False),
    sa.Column('created_by_agent', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('like_count', sa.Integer(), nullable=False),
    sa.Column('reply_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('heat_score', sa.Float(), server_default='0', nullable=False),
    sa.Column('heat_score_updated_at', sa.DateTime(), nullable=True),
    sa.Column('moderation_status', sa.String(length=20), server_default='active', nullable=False),
    sa.Column('archived_at', sa.DateTime(), nullable=True),
    sa.Column('archived_by_admin_id', sa.Integer(), nullable=True),
    sa.Column('archive_reason', sa.Text(), nullable=True),
    sa.CheckConstraint('length(content) <= 1000', name='ck_comments_content_length'),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['parent_id'], ['comments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['root_comment_id'], ['comments.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_comments_moderation_status', 'comments', ['moderation_status', 'created_at', 'id'], unique=False)
    op.create_index('idx_comments_post_parent_heat', 'comments', ['post_id', 'parent_id', 'heat_score', 'created_at', 'id'], unique=False)
    op.create_index('idx_comments_post_parent_latest', 'comments', ['post_id', 'parent_id', 'created_at', 'id'], unique=False)
    op.create_index('idx_comments_post_root_heat', 'comments', ['post_id', 'root_comment_id', 'heat_score', 'created_at', 'id'], unique=False)
    op.create_index('idx_comments_post_root_latest', 'comments', ['post_id', 'root_comment_id', 'created_at', 'id'], unique=False)
    op.create_index(op.f('ix_comments_id'), 'comments', ['id'], unique=False)
    op.create_index(op.f('ix_comments_owner_id'), 'comments', ['owner_id'], unique=False)
    op.create_index(op.f('ix_comments_parent_id'), 'comments', ['parent_id'], unique=False)
    op.create_index(op.f('ix_comments_post_id'), 'comments', ['post_id'], unique=False)
    op.create_index(op.f('ix_comments_root_comment_id'), 'comments', ['root_comment_id'], unique=False)
    op.create_table('likes',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('created_by_agent', sa.Boolean(), server_default='0', nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'post_id', name='likes_pkey')
    )
    op.create_index('idx_likes_post_id', 'likes', ['post_id'], unique=False)
    op.create_index('idx_likes_user_id', 'likes', ['user_id'], unique=False)
    op.create_table('poll_options',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('text', sa.String(length=20), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('vote_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('post_id', 'position', name='uq_poll_options_post_position')
    )
    op.create_index('idx_poll_options_post_position', 'poll_options', ['post_id', 'position'], unique=False)
    op.create_index(op.f('ix_poll_options_id'), 'poll_options', ['id'], unique=False)
    op.create_index(op.f('ix_poll_options_post_id'), 'poll_options', ['post_id'], unique=False)
    op.create_table('post_topics',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('topic_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('post_id', 'topic_id', name='uq_post_topics_post_topic')
    )
    op.create_index('idx_post_topics_topic_post', 'post_topics', ['topic_id', 'post_id'], unique=False)
    op.create_index(op.f('ix_post_topics_id'), 'post_topics', ['id'], unique=False)
    op.create_index(op.f('ix_post_topics_post_id'), 'post_topics', ['post_id'], unique=False)
    op.create_index(op.f('ix_post_topics_topic_id'), 'post_topics', ['topic_id'], unique=False)
    op.create_table('comment_likes',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('comment_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('created_by_agent', sa.Boolean(), server_default='0', nullable=False),
    sa.ForeignKeyConstraint(['comment_id'], ['comments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'comment_id', name='comment_likes_pkey')
    )
    op.create_index('idx_comment_likes_comment_id', 'comment_likes', ['comment_id'], unique=False)
    op.create_index('idx_comment_likes_user_id', 'comment_likes', ['user_id'], unique=False)
    op.create_table('content_reports',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reporter_id', sa.Integer(), nullable=False),
    sa.Column('target_type', sa.String(length=20), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=True),
    sa.Column('comment_id', sa.Integer(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=30), server_default='pending', nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('created_by_agent', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('reviewed_by_admin_id', sa.Integer(), nullable=True),
    sa.Column('escalation_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['comment_id'], ['comments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['escalation_id'], ['content_report_escalations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reporter_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by_admin_id'], ['platform_admin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_content_reports_comment_status', 'content_reports', ['comment_id', 'status'], unique=False)
    op.create_index('idx_content_reports_post_status', 'content_reports', ['post_id', 'status'], unique=False)
    op.create_index('idx_content_reports_reporter_comment_status', 'content_reports', ['reporter_id', 'comment_id', 'status'], unique=False)
    op.create_index('idx_content_reports_reporter_post_status', 'content_reports', ['reporter_id', 'post_id', 'status'], unique=False)
    op.create_index('idx_content_reports_reporter_user_status', 'content_reports', ['reporter_id', 'user_id', 'status'], unique=False)
    op.create_index('idx_content_reports_user_status', 'content_reports', ['user_id', 'status'], unique=False)
    op.create_index(op.f('ix_content_reports_comment_id'), 'content_reports', ['comment_id'], unique=False)
    op.create_index(op.f('ix_content_reports_created_at'), 'content_reports', ['created_at'], unique=False)
    op.create_index(op.f('ix_content_reports_escalation_id'), 'content_reports', ['escalation_id'], unique=False)
    op.create_index(op.f('ix_content_reports_id'), 'content_reports', ['id'], unique=False)
    op.create_index(op.f('ix_content_reports_post_id'), 'content_reports', ['post_id'], unique=False)
    op.create_index(op.f('ix_content_reports_reporter_id'), 'content_reports', ['reporter_id'], unique=False)
    op.create_index(op.f('ix_content_reports_reviewed_by_admin_id'), 'content_reports', ['reviewed_by_admin_id'], unique=False)
    op.create_index(op.f('ix_content_reports_status'), 'content_reports', ['status'], unique=False)
    op.create_index(op.f('ix_content_reports_target_type'), 'content_reports', ['target_type'], unique=False)
    op.create_index(op.f('ix_content_reports_user_id'), 'content_reports', ['user_id'], unique=False)
    op.create_table('notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recipient_id', sa.Integer(), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=True),
    sa.Column('type', sa.String(length=50), nullable=False),
    sa.Column('resource_type', sa.String(length=50), nullable=False),
    sa.Column('resource_id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=True),
    sa.Column('comment_id', sa.Integer(), nullable=True),
    sa.Column('source_content', sa.Text(), nullable=True),
    sa.Column('is_read', sa.Integer(), nullable=False),
    sa.Column('created_by_agent', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['comment_id'], ['comments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_notifications_recipient_created', 'notifications', ['recipient_id', 'created_at'], unique=False)
    op.create_index('idx_notifications_recipient_read_created', 'notifications', ['recipient_id', 'is_read', 'created_at'], unique=False)
    op.create_index('idx_notifications_resource', 'notifications', ['resource_type', 'resource_id'], unique=False)
    op.create_index(op.f('ix_notifications_comment_id'), 'notifications', ['comment_id'], unique=False)
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    op.create_index(op.f('ix_notifications_id'), 'notifications', ['id'], unique=False)
    op.create_index(op.f('ix_notifications_is_read'), 'notifications', ['is_read'], unique=False)
    op.create_index(op.f('ix_notifications_post_id'), 'notifications', ['post_id'], unique=False)
    op.create_index(op.f('ix_notifications_recipient_id'), 'notifications', ['recipient_id'], unique=False)
    op.create_index(op.f('ix_notifications_resource_id'), 'notifications', ['resource_id'], unique=False)
    op.create_index(op.f('ix_notifications_resource_type'), 'notifications', ['resource_type'], unique=False)
    op.create_index(op.f('ix_notifications_sender_id'), 'notifications', ['sender_id'], unique=False)
    op.create_index(op.f('ix_notifications_type'), 'notifications', ['type'], unique=False)
    op.create_table('poll_votes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('option_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('created_by_agent', sa.Boolean(), server_default='0', nullable=False),
    sa.ForeignKeyConstraint(['option_id'], ['poll_options.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('post_id', 'user_id', name='uq_poll_votes_post_user')
    )
    op.create_index('idx_poll_votes_post_option', 'poll_votes', ['post_id', 'option_id'], unique=False)
    op.create_index(op.f('ix_poll_votes_id'), 'poll_votes', ['id'], unique=False)
    op.create_index(op.f('ix_poll_votes_option_id'), 'poll_votes', ['option_id'], unique=False)
    op.create_index(op.f('ix_poll_votes_post_id'), 'poll_votes', ['post_id'], unique=False)
    op.create_index(op.f('ix_poll_votes_user_id'), 'poll_votes', ['user_id'], unique=False)
    op.create_table('user_violation_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('violation_count', sa.Integer(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('source_type', sa.String(length=30), server_default='manual', nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=True),
    sa.Column('dedup_key', sa.String(length=100), nullable=True),
    sa.Column('notification_id', sa.Integer(), nullable=True),
    sa.Column('created_by_admin_id', sa.Integer(), nullable=True),
    sa.Column('restriction_until', sa.DateTime(), nullable=True),
    sa.Column('is_permanent', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('released_at', sa.DateTime(), nullable=True),
    sa.Column('violation_count_reversed_at', sa.DateTime(), nullable=True),
    sa.Column('released_by_admin_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_admin_id'], ['platform_admin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['notification_id'], ['notifications.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['released_by_admin_id'], ['platform_admin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_user_violation_events_user_category', 'user_violation_events', ['user_id', 'category', 'created_at'], unique=False)
    op.create_index(op.f('ix_user_violation_events_category'), 'user_violation_events', ['category'], unique=False)
    op.create_index(op.f('ix_user_violation_events_created_at'), 'user_violation_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_user_violation_events_created_by_admin_id'), 'user_violation_events', ['created_by_admin_id'], unique=False)
    op.create_index(op.f('ix_user_violation_events_dedup_key'), 'user_violation_events', ['dedup_key'], unique=True)
    op.create_index(op.f('ix_user_violation_events_id'), 'user_violation_events', ['id'], unique=False)
    op.create_index(op.f('ix_user_violation_events_notification_id'), 'user_violation_events', ['notification_id'], unique=False)
    op.create_index(op.f('ix_user_violation_events_user_id'), 'user_violation_events', ['user_id'], unique=False)
    op.create_table('moderation_appeals',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('notification_id', sa.Integer(), nullable=False),
    sa.Column('violation_event_id', sa.Integer(), nullable=True),
    sa.Column('appellant_id', sa.Integer(), nullable=False),
    sa.Column('target_type', sa.String(length=20), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=False),
    sa.Column('action_label', sa.String(length=100), nullable=False),
    sa.Column('moderation_reason', sa.Text(), nullable=True),
    sa.Column('appeal_reason', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=30), server_default='pending', nullable=False),
    sa.Column('reject_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('resolved_by_admin_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['appellant_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['notification_id'], ['notifications.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['resolved_by_admin_id'], ['platform_admin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['violation_event_id'], ['user_violation_events.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('notification_id', name='uq_moderation_appeals_notification_id')
    )
    op.create_index('idx_moderation_appeals_appellant_status', 'moderation_appeals', ['appellant_id', 'status'], unique=False)
    op.create_index('idx_moderation_appeals_target_status', 'moderation_appeals', ['target_type', 'target_id', 'status'], unique=False)
    op.create_index(op.f('ix_moderation_appeals_appellant_id'), 'moderation_appeals', ['appellant_id'], unique=False)
    op.create_index(op.f('ix_moderation_appeals_created_at'), 'moderation_appeals', ['created_at'], unique=False)
    op.create_index(op.f('ix_moderation_appeals_id'), 'moderation_appeals', ['id'], unique=False)
    op.create_index(op.f('ix_moderation_appeals_notification_id'), 'moderation_appeals', ['notification_id'], unique=True)
    op.create_index(op.f('ix_moderation_appeals_resolved_by_admin_id'), 'moderation_appeals', ['resolved_by_admin_id'], unique=False)
    op.create_index(op.f('ix_moderation_appeals_status'), 'moderation_appeals', ['status'], unique=False)
    op.create_index(op.f('ix_moderation_appeals_target_id'), 'moderation_appeals', ['target_id'], unique=False)
    op.create_index(op.f('ix_moderation_appeals_target_type'), 'moderation_appeals', ['target_type'], unique=False)
    op.create_index(op.f('ix_moderation_appeals_violation_event_id'), 'moderation_appeals', ['violation_event_id'], unique=False)


def downgrade() -> None:
    """按外键依赖的逆序删除当前公开平台的全部数据库对象。"""

    op.drop_index(op.f('ix_moderation_appeals_violation_event_id'), table_name='moderation_appeals')
    op.drop_index(op.f('ix_moderation_appeals_target_type'), table_name='moderation_appeals')
    op.drop_index(op.f('ix_moderation_appeals_target_id'), table_name='moderation_appeals')
    op.drop_index(op.f('ix_moderation_appeals_status'), table_name='moderation_appeals')
    op.drop_index(op.f('ix_moderation_appeals_resolved_by_admin_id'), table_name='moderation_appeals')
    op.drop_index(op.f('ix_moderation_appeals_notification_id'), table_name='moderation_appeals')
    op.drop_index(op.f('ix_moderation_appeals_id'), table_name='moderation_appeals')
    op.drop_index(op.f('ix_moderation_appeals_created_at'), table_name='moderation_appeals')
    op.drop_index(op.f('ix_moderation_appeals_appellant_id'), table_name='moderation_appeals')
    op.drop_index('idx_moderation_appeals_target_status', table_name='moderation_appeals')
    op.drop_index('idx_moderation_appeals_appellant_status', table_name='moderation_appeals')
    op.drop_table('moderation_appeals')
    op.drop_index(op.f('ix_user_violation_events_user_id'), table_name='user_violation_events')
    op.drop_index(op.f('ix_user_violation_events_notification_id'), table_name='user_violation_events')
    op.drop_index(op.f('ix_user_violation_events_id'), table_name='user_violation_events')
    op.drop_index(op.f('ix_user_violation_events_dedup_key'), table_name='user_violation_events')
    op.drop_index(op.f('ix_user_violation_events_created_by_admin_id'), table_name='user_violation_events')
    op.drop_index(op.f('ix_user_violation_events_created_at'), table_name='user_violation_events')
    op.drop_index(op.f('ix_user_violation_events_category'), table_name='user_violation_events')
    op.drop_index('idx_user_violation_events_user_category', table_name='user_violation_events')
    op.drop_table('user_violation_events')
    op.drop_index(op.f('ix_poll_votes_user_id'), table_name='poll_votes')
    op.drop_index(op.f('ix_poll_votes_post_id'), table_name='poll_votes')
    op.drop_index(op.f('ix_poll_votes_option_id'), table_name='poll_votes')
    op.drop_index(op.f('ix_poll_votes_id'), table_name='poll_votes')
    op.drop_index('idx_poll_votes_post_option', table_name='poll_votes')
    op.drop_table('poll_votes')
    op.drop_index(op.f('ix_notifications_type'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_sender_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_resource_type'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_resource_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_recipient_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_post_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_is_read'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_comment_id'), table_name='notifications')
    op.drop_index('idx_notifications_resource', table_name='notifications')
    op.drop_index('idx_notifications_recipient_read_created', table_name='notifications')
    op.drop_index('idx_notifications_recipient_created', table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_content_reports_user_id'), table_name='content_reports')
    op.drop_index(op.f('ix_content_reports_target_type'), table_name='content_reports')
    op.drop_index(op.f('ix_content_reports_status'), table_name='content_reports')
    op.drop_index(op.f('ix_content_reports_reviewed_by_admin_id'), table_name='content_reports')
    op.drop_index(op.f('ix_content_reports_reporter_id'), table_name='content_reports')
    op.drop_index(op.f('ix_content_reports_post_id'), table_name='content_reports')
    op.drop_index(op.f('ix_content_reports_id'), table_name='content_reports')
    op.drop_index(op.f('ix_content_reports_escalation_id'), table_name='content_reports')
    op.drop_index(op.f('ix_content_reports_created_at'), table_name='content_reports')
    op.drop_index(op.f('ix_content_reports_comment_id'), table_name='content_reports')
    op.drop_index('idx_content_reports_user_status', table_name='content_reports')
    op.drop_index('idx_content_reports_reporter_user_status', table_name='content_reports')
    op.drop_index('idx_content_reports_reporter_post_status', table_name='content_reports')
    op.drop_index('idx_content_reports_reporter_comment_status', table_name='content_reports')
    op.drop_index('idx_content_reports_post_status', table_name='content_reports')
    op.drop_index('idx_content_reports_comment_status', table_name='content_reports')
    op.drop_table('content_reports')
    op.drop_index('idx_comment_likes_user_id', table_name='comment_likes')
    op.drop_index('idx_comment_likes_comment_id', table_name='comment_likes')
    op.drop_table('comment_likes')
    op.drop_index(op.f('ix_post_topics_topic_id'), table_name='post_topics')
    op.drop_index(op.f('ix_post_topics_post_id'), table_name='post_topics')
    op.drop_index(op.f('ix_post_topics_id'), table_name='post_topics')
    op.drop_index('idx_post_topics_topic_post', table_name='post_topics')
    op.drop_table('post_topics')
    op.drop_index(op.f('ix_poll_options_post_id'), table_name='poll_options')
    op.drop_index(op.f('ix_poll_options_id'), table_name='poll_options')
    op.drop_index('idx_poll_options_post_position', table_name='poll_options')
    op.drop_table('poll_options')
    op.drop_index('idx_likes_user_id', table_name='likes')
    op.drop_index('idx_likes_post_id', table_name='likes')
    op.drop_table('likes')
    op.drop_index(op.f('ix_comments_root_comment_id'), table_name='comments')
    op.drop_index(op.f('ix_comments_post_id'), table_name='comments')
    op.drop_index(op.f('ix_comments_parent_id'), table_name='comments')
    op.drop_index(op.f('ix_comments_owner_id'), table_name='comments')
    op.drop_index(op.f('ix_comments_id'), table_name='comments')
    op.drop_index('idx_comments_post_root_latest', table_name='comments')
    op.drop_index('idx_comments_post_root_heat', table_name='comments')
    op.drop_index('idx_comments_post_parent_latest', table_name='comments')
    op.drop_index('idx_comments_post_parent_heat', table_name='comments')
    op.drop_index('idx_comments_moderation_status', table_name='comments')
    op.drop_table('comments')
    op.drop_index(op.f('ix_registration_invitations_used_by_user_id'), table_name='registration_invitations')
    op.drop_index(op.f('ix_registration_invitations_id'), table_name='registration_invitations')
    op.drop_index(op.f('ix_registration_invitations_email'), table_name='registration_invitations')
    op.drop_index(op.f('ix_registration_invitations_created_by_admin_id'), table_name='registration_invitations')
    op.drop_index(op.f('ix_registration_invitations_code'), table_name='registration_invitations')
    op.drop_table('registration_invitations')
    op.drop_index(op.f('ix_posts_repost_root_post_id'), table_name='posts')
    op.drop_index(op.f('ix_posts_id'), table_name='posts')
    op.drop_index('idx_posts_moderation_status', table_name='posts')
    op.drop_index('idx_posts_latest', table_name='posts')
    op.drop_index('idx_posts_heat_latest', table_name='posts')
    op.drop_index('idx_posts_author_latest', table_name='posts')
    op.drop_table('posts')
    op.drop_index(op.f('ix_platform_user_moderations_user_id'), table_name='platform_user_moderations')
    op.drop_table('platform_user_moderations')
    op.drop_index(op.f('ix_hot_topics_id'), table_name='hot_topics')
    op.drop_index(op.f('ix_hot_topics_generation_id'), table_name='hot_topics')
    op.drop_index('idx_hot_topics_public_order', table_name='hot_topics')
    op.drop_index('idx_hot_topics_generation_status', table_name='hot_topics')
    op.drop_table('hot_topics')
    op.drop_index(op.f('ix_follows_id'), table_name='follows')
    op.drop_index('idx_follow_following_id', table_name='follows')
    op.drop_index('idx_follow_follower_id', table_name='follows')
    op.drop_table('follows')
    op.drop_index(op.f('ix_email_verification_codes_user_id'), table_name='email_verification_codes')
    op.drop_index(op.f('ix_email_verification_codes_id'), table_name='email_verification_codes')
    op.drop_index(op.f('ix_email_verification_codes_email'), table_name='email_verification_codes')
    op.drop_index(op.f('ix_email_verification_codes_code'), table_name='email_verification_codes')
    op.drop_table('email_verification_codes')
    op.drop_index(op.f('ix_content_report_escalations_user_id'), table_name='content_report_escalations')
    op.drop_index(op.f('ix_content_report_escalations_status'), table_name='content_report_escalations')
    op.drop_index(op.f('ix_content_report_escalations_reviewed_by_admin_id'), table_name='content_report_escalations')
    op.drop_index(op.f('ix_content_report_escalations_id'), table_name='content_report_escalations')
    op.drop_index(op.f('ix_content_report_escalations_created_at'), table_name='content_report_escalations')
    op.drop_index('idx_content_report_escalations_user_status', table_name='content_report_escalations')
    op.drop_table('content_report_escalations')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_user_sessions_session_id'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_scope'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_revoked_at'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_refresh_token_hash'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_id'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_expires_at'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_client_type'), table_name='user_sessions')
    op.drop_index('ix_user_sessions_account_scope_client', table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_account_id'), table_name='user_sessions')
    op.drop_table('user_sessions')
    op.drop_index(op.f('ix_topics_name'), table_name='topics')
    op.drop_index(op.f('ix_topics_id'), table_name='topics')
    op.drop_index('idx_topics_heat', table_name='topics')
    op.drop_table('topics')
    op.drop_index(op.f('ix_platform_admin_users_username'), table_name='platform_admin_users')
    op.drop_index(op.f('ix_platform_admin_users_id'), table_name='platform_admin_users')
    op.drop_table('platform_admin_users')
    op.drop_index(op.f('ix_platform_admin_operation_logs_target_type'), table_name='platform_admin_operation_logs')
    op.drop_index(op.f('ix_platform_admin_operation_logs_target_id'), table_name='platform_admin_operation_logs')
    op.drop_index(op.f('ix_platform_admin_operation_logs_operator_id'), table_name='platform_admin_operation_logs')
    op.drop_index(op.f('ix_platform_admin_operation_logs_id'), table_name='platform_admin_operation_logs')
    op.drop_index(op.f('ix_platform_admin_operation_logs_created_at'), table_name='platform_admin_operation_logs')
    op.drop_index(op.f('ix_platform_admin_operation_logs_action'), table_name='platform_admin_operation_logs')
    op.drop_table('platform_admin_operation_logs')
    op.drop_table('hot_topic_settings')
    op.drop_index(op.f('ix_hot_topic_generations_id'), table_name='hot_topic_generations')
    op.drop_table('hot_topic_generations')
    op.drop_table('content_moderation_llm_settings')
