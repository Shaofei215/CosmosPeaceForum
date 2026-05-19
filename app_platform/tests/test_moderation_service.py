from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app_platform.app.admin.models import PlatformAdminOperationLog, PlatformAdminUser, UserModeration
from app_platform.app.admin.schemas import UserModerationUpdateRequest
from app_platform.app.admin.services.moderation_guard import ensure_account_available
from app_platform.app.admin.services.moderation_service import (
    delete_post_as_admin,
    update_user_moderation,
)
from app_platform.app.db.session import Base
from app_platform.app.models import Notification, Post, User


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
    admin = PlatformAdminUser(
        username="admin",
        email="appeal@example.com",
        password_hash="hashed",
        is_super_admin=True,
    )
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
    assert notifications[0].source_content.endswith("如有异议，请向appeal@example.com申诉。")

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
    assert notifications[0].source_content.endswith("如有异议，请向appeal@example.com申诉。")


def test_action_restrictions_can_be_removed_with_explicit_null(db_session):
    user, admin = _seed_user_and_admin(db_session)
    until = datetime.utcnow() + timedelta(days=3)

    update_user_moderation(
        db_session,
        user.id,
        UserModerationUpdateRequest(
            publish_banned_until=until,
            publish_ban_reason="刷屏",
            comment_banned_until=until,
            comment_ban_reason="刷屏",
            interaction_banned_until=until,
            interaction_ban_reason="刷屏",
        ),
        admin,
    )
    db_session.query(Notification).delete()
    db_session.commit()

    moderation = update_user_moderation(
        db_session,
        user.id,
        UserModerationUpdateRequest(
            publish_banned_until=None,
            comment_banned_until=None,
            interaction_banned_until=None,
        ),
        admin,
    )

    assert moderation.publish_banned_until is None
    assert moderation.publish_ban_reason is None
    assert moderation.comment_banned_until is None
    assert moderation.comment_ban_reason is None
    assert moderation.interaction_banned_until is None
    assert moderation.interaction_ban_reason is None

    notice_contents = [
        notification.source_content for notification in db_session.query(Notification).all()
    ]
    assert notice_contents == [
        "你的发帖功能限制已解除。",
        "你的评论功能限制已解除。",
        "你的互动功能限制已解除。",
    ]


def test_account_ban_login_detail_includes_admin_appeal_email(db_session):
    user, admin = _seed_user_and_admin(db_session)

    update_user_moderation(
        db_session,
        user.id,
        UserModerationUpdateRequest(account_banned=True, account_ban_reason="严重违规"),
        admin,
    )

    with pytest.raises(HTTPException) as exc_info:
        ensure_account_available(db_session, user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "严重违规\n如有异议，请向appeal@example.com申诉。"


def test_moderation_notice_keeps_long_reason_without_original_content(db_session):
    user, admin = _seed_user_and_admin(db_session)
    post = Post(author_id=user.id, content="这段原内容不应该进入管理通知")
    db_session.add(post)
    db_session.commit()

    long_reason = "违规原因" + "很长" * 260
    delete_post_as_admin(db_session, post.id, admin, reason=long_reason, notify_author=True)

    notification = db_session.query(Notification).one()
    assert notification.source_content == f"你的内容因违反社区规则已被管理端处理。\n原因：{long_reason}"
    assert "原内容" not in notification.source_content
    assert "这段原内容不应该进入管理通知" not in notification.source_content
