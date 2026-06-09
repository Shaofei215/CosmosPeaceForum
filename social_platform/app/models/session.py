"""公开平台服务端 session 模型。

user_sessions 同时服务真人用户、AI Agent 和平台内管理员；scope 区分身份域，
client_type 区分 mobile/desktop/agent，用于真人同端互斥和会话列表展示。
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text

from social_platform.app.db.session import Base


class UserSession(Base):
    """公开平台账号会话，保存可撤销 session 与 refresh token 哈希。"""

    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    scope = Column(String(32), nullable=False, index=True)
    client_type = Column(String(32), nullable=False, index=True)
    refresh_token_hash = Column(String(64), nullable=False, unique=True, index=True)
    revoked_at = Column(DateTime, nullable=True, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    remember_me = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


Index(
    "ix_user_sessions_account_scope_client",
    UserSession.account_id,
    UserSession.scope,
    UserSession.client_type,
)
