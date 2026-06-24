from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from social_platform.app.admin.models import PlatformAdminOperationLog, PlatformAdminUser, UserModeration
from social_platform.app.admin.schemas import UserModerationUpdateRequest
from social_platform.app.admin.services.moderation_guard import ensure_account_available
from social_platform.app.admin.services.moderation_service import update_user_moderation
from social_platform.app.domains.content_safety.application import create_content_report
from social_platform.app.domains.content_safety import llm_moderation as content_moderation_llm_service
from social_platform.app.domains.content_safety.admin_application import (
    ban_reported_user_as_admin,
    delete_post_as_admin,
    delete_reported_post_as_admin,
    list_reported_content,
    list_reported_users,
    release_reported_content,
    release_reported_user,
)
from social_platform.app.domains.content_safety.appeal_application import is_notification_appealable
from social_platform.app.db.session import Base
from social_platform.app.domains.comment.models import Comment
from social_platform.app.domains.notification.models import Notification
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.user.models import User
from social_platform.app.domains.content_safety.models import ContentReport


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
    assert notifications[0].source_content == "你的账号已被永久封禁。\n原因：违规测试"

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
    assert "appeal@example.com" not in notifications[0].source_content


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


def test_account_ban_operation_detail_excludes_admin_appeal_email(db_session):
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
    assert exc_info.value.detail == "严重违规"


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


def test_appeal_result_notice_is_not_appealable(db_session):
    user, _ = _seed_user_and_admin(db_session)
    post = Post(author_id=user.id, content="被处理内容")
    db_session.add(post)
    db_session.flush()
    moderation_notice = Notification(
        recipient_id=user.id,
        sender_id=None,
        type="moderation",
        resource_type="post",
        resource_id=post.id,
        source_content="你的内容因违反社区规则已被管理端处理。\n原因：违规",
    )
    appeal_result_notice = Notification(
        recipient_id=user.id,
        sender_id=None,
        type="moderation",
        resource_type="post",
        resource_id=post.id,
        source_content="你的申诉已通过，相关内容已恢复公开。",
    )
    db_session.add_all([moderation_notice, appeal_result_notice])
    db_session.flush()

    assert is_notification_appealable(db_session, moderation_notice, user.id) is True
    assert is_notification_appealable(db_session, appeal_result_notice, user.id) is False


def test_create_content_report_for_post_and_comment_deduplicates_pending_report(db_session):
    author, _ = _seed_user_and_admin(db_session)
    reporter = User(username="reporter")
    post = Post(author_id=author.id, content="被举报帖子")
    db_session.add_all([reporter, post])
    db_session.commit()
    comment = Comment(post_id=post.id, owner_id=author.id, content="被举报评论")
    db_session.add(comment)
    db_session.commit()

    first = create_content_report(db_session, reporter, "post", post.id, "垃圾内容")
    second = create_content_report(db_session, reporter, "post", post.id, "更新后的原因")
    comment_report = create_content_report(db_session, reporter, "comment", comment.id, "评论违规")

    assert first.id == second.id
    assert second.reason == "更新后的原因"
    assert comment_report.comment_id == comment.id
    assert db_session.query(ContentReport).filter(ContentReport.status == "pending").count() == 2


def test_reported_content_list_groups_by_content_and_sorts_by_report_count(db_session):
    author, _ = _seed_user_and_admin(db_session)
    reporter_a = User(username="reporter_a")
    reporter_b = User(username="reporter_b")
    reporter_c = User(username="reporter_c")
    post_one = Post(author_id=author.id, content="多人举报")
    post_two = Post(author_id=author.id, content="单人举报")
    db_session.add_all([reporter_a, reporter_b, reporter_c, post_one, post_two])
    db_session.commit()

    create_content_report(db_session, reporter_a, "post", post_two.id, "原因 C")
    create_content_report(db_session, reporter_b, "post", post_one.id, "原因 A")
    create_content_report(db_session, reporter_c, "post", post_one.id, "原因 B")

    items, total = list_reported_content(db_session, content_type=None, skip=0, limit=10)

    assert total == 2
    assert items[0].id == post_one.id
    assert items[0].report_count == 2
    assert {reason.reason for reason in items[0].report_reasons} == {"原因 A", "原因 B"}
    assert items[1].id == post_two.id
    assert items[1].report_count == 1


def test_release_reported_content_removes_item_from_pending_review_without_deleting(db_session):
    author, admin = _seed_user_and_admin(db_session)
    reporter = User(username="release_reporter")
    post = Post(author_id=author.id, content="待放行内容")
    db_session.add_all([reporter, post])
    db_session.commit()
    create_content_report(db_session, reporter, "post", post.id, "误报待确认")

    released_count = release_reported_content(db_session, "post", post.id, admin)
    items, total = list_reported_content(db_session, content_type=None, skip=0, limit=10)

    assert released_count == 1
    assert total == 0
    assert items == []
    assert db_session.query(Post).filter(Post.id == post.id).first() is not None
    report = db_session.query(ContentReport).one()
    assert report.status == "released"
    assert report.reviewed_by_admin_id == admin.id


def test_delete_reported_content_notifies_author_with_reason_and_reporters_without_reason(db_session):
    author, admin = _seed_user_and_admin(db_session)
    reporter_a = User(username="delete_reporter_a")
    reporter_b = User(username="delete_reporter_b")
    post = Post(author_id=author.id, content="确认违规内容")
    db_session.add_all([reporter_a, reporter_b, post])
    db_session.commit()
    create_content_report(db_session, reporter_a, "post", post.id, "违规线索 A")
    create_content_report(db_session, reporter_b, "post", post.id, "违规线索 B")

    delete_reported_post_as_admin(db_session, post.id, admin, reason="广告引流", notify_author=True)

    notifications = db_session.query(Notification).order_by(Notification.recipient_id).all()
    by_recipient = {notification.recipient_id: notification.source_content for notification in notifications}
    assert "原因：广告引流" in by_recipient[author.id]
    assert by_recipient[reporter_a.id] == "你举报的目标存在违规，已被管理端处理。"
    assert by_recipient[reporter_b.id] == "你举报的目标存在违规，已被管理端处理。"
    assert "广告引流" not in by_recipient[reporter_a.id]
    archived_post = db_session.query(Post).filter(Post.id == post.id).one()
    assert archived_post.moderation_status == "archived"
    assert archived_post.archive_reason == "广告引流"


def test_create_user_report_deduplicates_pending_report(db_session):
    target, _ = _seed_user_and_admin(db_session)
    reporter = User(username="user_reporter")
    db_session.add(reporter)
    db_session.commit()

    first = create_content_report(db_session, reporter, "user", target.id, "资料违规")
    second = create_content_report(db_session, reporter, "user", target.id, "持续骚扰")

    assert first.id == second.id
    assert second.user_id == target.id
    assert second.reason == "持续骚扰"
    assert db_session.query(ContentReport).filter(ContentReport.status == "pending").count() == 1


def test_reported_users_list_groups_by_user_and_sorts_by_report_count(db_session):
    target_one, _ = _seed_user_and_admin(db_session)
    target_two = User(username="target_two", bio="待审签名")
    reporter_a = User(username="user_reporter_a")
    reporter_b = User(username="user_reporter_b")
    reporter_c = User(username="user_reporter_c")
    db_session.add_all([target_two, reporter_a, reporter_b, reporter_c])
    db_session.commit()

    create_content_report(db_session, reporter_a, "user", target_two.id, "原因 C")
    create_content_report(db_session, reporter_b, "user", target_one.id, "原因 A")
    create_content_report(db_session, reporter_c, "user", target_one.id, "原因 B")

    items, total = list_reported_users(db_session, skip=0, limit=10)

    assert total == 2
    assert items[0].id == target_one.id
    assert items[0].report_count == 2
    assert {reason.reason for reason in items[0].report_reasons} == {"原因 A", "原因 B"}
    assert items[1].id == target_two.id
    assert items[1].bio == "待审签名"


def test_release_reported_user_removes_item_from_pending_review(db_session):
    target, admin = _seed_user_and_admin(db_session)
    reporter = User(username="release_user_reporter")
    db_session.add(reporter)
    db_session.commit()
    create_content_report(db_session, reporter, "user", target.id, "误报用户")

    released_count = release_reported_user(db_session, target.id, admin)
    items, total = list_reported_users(db_session, skip=0, limit=10)

    assert released_count == 1
    assert total == 0
    assert items == []
    assert db_session.query(User).filter(User.id == target.id).first() is not None
    report = db_session.query(ContentReport).one()
    assert report.status == "released"
    assert report.reviewed_by_admin_id == admin.id


def test_ban_reported_user_confirms_reports_and_notifies(db_session):
    target, admin = _seed_user_and_admin(db_session)
    reporter = User(username="ban_user_reporter")
    db_session.add(reporter)
    db_session.commit()
    create_content_report(db_session, reporter, "user", target.id, "账号违规")

    ban_reported_user_as_admin(db_session, target.id, admin, reason="持续骚扰", notify_user=True)

    report = db_session.query(ContentReport).one()
    assert report.status == "confirmed"
    moderation = db_session.query(UserModeration).filter(UserModeration.user_id == target.id).one()
    assert moderation.account_ban_reason == "持续骚扰"
    notifications = db_session.query(Notification).order_by(Notification.recipient_id).all()
    by_recipient = {notification.recipient_id: notification.source_content for notification in notifications}
    assert "持续骚扰" in by_recipient[target.id]
    assert by_recipient[reporter.id] == "你举报的目标存在违规，已被管理端处理。"



class _FakeLLMResponse:
    def __init__(self, content):
        self.content = content


class _FakeLLM:
    def __init__(self, content):
        self.content = content
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return _FakeLLMResponse(self.content)


def _enable_content_moderation_llm(db_session):
    settings = content_moderation_llm_service.get_content_moderation_llm_settings(db_session)
    settings.enabled = True
    settings.llm_model_name = "test-model"
    settings.llm_api_key = "test-key"
    db_session.add(settings)
    db_session.commit()
    return settings


def test_content_moderation_llm_pass_releases_reported_content(db_session):
    author, _ = _seed_user_and_admin(db_session)
    reporter = User(username="llm_pass_reporter")
    post = Post(author_id=author.id, content="正常讨论内容")
    db_session.add_all([reporter, post])
    db_session.commit()
    report = create_content_report(db_session, reporter, "post", post.id, "误报")
    _enable_content_moderation_llm(db_session)

    decision, reason = content_moderation_llm_service.review_report(
        db_session,
        report.id,
        llm_factory=lambda settings: _FakeLLM("pass"),
    )

    assert decision == "pass"
    assert reason is None
    stored_report = db_session.query(ContentReport).filter(ContentReport.id == report.id).one()
    assert stored_report.status == "released"
    assert stored_report.reviewed_by_admin.username == "llm_moderator"
    assert db_session.query(Post).filter(Post.id == post.id).first() is not None


def test_content_moderation_llm_delete_removes_reported_post(db_session):
    author, _ = _seed_user_and_admin(db_session)
    reporter = User(username="llm_delete_reporter")
    post = Post(author_id=author.id, content="诈骗广告内容")
    db_session.add_all([reporter, post])
    db_session.commit()
    report = create_content_report(db_session, reporter, "post", post.id, "广告")
    _enable_content_moderation_llm(db_session)

    decision, reason = content_moderation_llm_service.review_report(
        db_session,
        report.id,
        llm_factory=lambda settings: _FakeLLM("delete 诈骗广告引流"),
    )

    assert decision == "delete"
    assert reason == "诈骗广告引流"
    archived_post = db_session.query(Post).filter(Post.id == post.id).one()
    assert archived_post.moderation_status == "archived"
    assert archived_post.archive_reason == "诈骗广告引流"
    notification = db_session.query(Notification).filter(Notification.recipient_id == author.id).one()
    assert "诈骗广告引流" in notification.source_content


def test_content_moderation_llm_drop_keeps_report_pending(db_session):
    author, _ = _seed_user_and_admin(db_session)
    reporter = User(username="llm_drop_reporter")
    post = Post(author_id=author.id, content="语义有争议的内容")
    db_session.add_all([reporter, post])
    db_session.commit()
    report = create_content_report(db_session, reporter, "post", post.id, "需要人工确认")
    _enable_content_moderation_llm(db_session)

    decision, reason = content_moderation_llm_service.review_report(
        db_session,
        report.id,
        llm_factory=lambda settings: _FakeLLM("drop"),
    )

    assert decision == "drop"
    assert reason is None
    stored_report = db_session.query(ContentReport).filter(ContentReport.id == report.id).one()
    assert stored_report.status == "pending"
    log = db_session.query(PlatformAdminOperationLog).filter(
        PlatformAdminOperationLog.action == "content_moderation_llm_drop"
    ).one()
    assert log.operator_username == "llm_moderator"


def test_content_moderation_llm_comment_context_includes_post_and_parent_comment(db_session):
    author, _ = _seed_user_and_admin(db_session)
    reporter = User(username="llm_context_reporter")
    post = Post(author_id=author.id, title="上下文帖子", content="帖子正文")
    db_session.add_all([reporter, post])
    db_session.commit()
    parent = Comment(post_id=post.id, owner_id=author.id, content="父评论")
    db_session.add(parent)
    db_session.commit()
    comment = Comment(
        post_id=post.id,
        owner_id=author.id,
        parent_id=parent.id,
        root_comment_id=parent.id,
        content="被举报回复",
    )
    db_session.add(comment)
    db_session.commit()
    report = create_content_report(db_session, reporter, "comment", comment.id, "回复违规")

    context = content_moderation_llm_service.build_report_context(db_session, report)

    assert context["target_comment"]["id"] == comment.id
    assert context["post"]["id"] == post.id
    assert context["post"]["content"] == "帖子正文"
    assert context["parent_comment"]["id"] == parent.id
    assert context["parent_comment"]["content"] == "父评论"


def test_content_moderation_llm_user_context_includes_recent_contents(db_session):
    target, _ = _seed_user_and_admin(db_session)
    reporter = User(username="llm_user_context_reporter")
    db_session.add(reporter)
    db_session.commit()
    post = Post(author_id=target.id, title="近期帖子", content="帖子内容")
    db_session.add(post)
    db_session.commit()
    comment = Comment(post_id=post.id, owner_id=target.id, content="近期评论")
    db_session.add(comment)
    db_session.commit()
    report = create_content_report(db_session, reporter, "user", target.id, "账号违规")

    context = content_moderation_llm_service.build_report_context(db_session, report)

    assert context["target_user"]["id"] == target.id
    assert context["target_user"]["username"] == "target_user"
    assert len(context["recent_posts"]) == 1
    assert len(context["recent_comments"]) == 1
    assert context["recent_posts"][0]["type"] == "post"
    assert context["recent_comments"][0]["type"] == "comment"


def test_content_moderation_llm_delete_bans_reported_user(db_session):
    target, _ = _seed_user_and_admin(db_session)
    reporter = User(username="llm_user_delete_reporter")
    db_session.add(reporter)
    db_session.commit()
    report = create_content_report(db_session, reporter, "user", target.id, "骚扰")
    _enable_content_moderation_llm(db_session)

    decision, reason = content_moderation_llm_service.review_report(
        db_session,
        report.id,
        llm_factory=lambda settings: _FakeLLM("delete 持续骚扰用户"),
    )

    assert decision == "delete"
    assert reason == "持续骚扰用户"
    stored_report = db_session.query(ContentReport).filter(ContentReport.id == report.id).one()
    assert stored_report.status == "confirmed"
    moderation = db_session.query(UserModeration).filter(UserModeration.user_id == target.id).one()
    assert moderation.account_ban_reason == "持续骚扰用户"


def test_content_moderation_llm_prompt_requires_strict_output():
    settings = content_moderation_llm_service.ContentModerationLLMSettings()
    prompt = content_moderation_llm_service.serialize_prompt_config(settings)["default_value"]

    assert "pass" in prompt
    assert "delete {处理原因}" in prompt
    assert "drop" in prompt
    assert "不能输出解释" in prompt
