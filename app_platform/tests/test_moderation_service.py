from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app_platform.app.admin.models import PlatformAdminOperationLog, PlatformAdminUser, UserModeration
from app_platform.app.admin.schemas import UserModerationUpdateRequest
from app_platform.app.admin.services.moderation_service import update_user_moderation
from app_platform.app.db.session import Base
from app_platform.app.models import Notification, User


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def _seed_user_and_admin(db_session):
    user = User(username="target_user")
    admin = PlatformAdminUser(username="admin", password_hash="hashed", is_super_admin=True)
    db_session.add_all([user, admin])
    db_session.commit()
    return user, admin


def test_account_ban_creates_moderation_notification(db_session):
    user, admin = _seed_user_and_admin(db_session)

    update_user_moderation(
        db_session,
        user.id,
        UserModerationUpdateRequest(account_banned=True, account_ban_reason="违规测试"),
        admin,
    )

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1
    assert notifications[0].recipient_id == user.id
    assert notifications[0].sender_id is None
    assert notifications[0].type == "moderation"
    assert notifications[0].resource_type == "user"
    assert notifications[0].resource_id == user.id
    assert "你的账号已被永久封禁" in notifications[0].source_content
    assert "违规测试" in notifications[0].source_content

    assert db_session.query(UserModeration).count() == 1
    assert db_session.query(PlatformAdminOperationLog).count() == 1


def test_repeated_same_moderation_save_does_not_duplicate_notifications(db_session):
    user, admin = _seed_user_and_admin(db_session)
    until = datetime.utcnow() + timedelta(days=3)
    request = UserModerationUpdateRequest(
        publish_banned_until=until,
        publish_ban_reason="刷屏",
    )

    update_user_moderation(db_session, user.id, request, admin)
    update_user_moderation(db_session, user.id, request, admin)

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1
    assert notifications[0].type == "moderation"
    assert "你的发帖功能已被限制至" in notifications[0].source_content
    assert "刷屏" in notifications[0].source_content
