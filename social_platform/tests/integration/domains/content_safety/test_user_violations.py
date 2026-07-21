"""用户违规分级处罚、资料撤下、去重与事件解除规则测试。"""

from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from social_platform.app.admin.models import PlatformAdminUser, UserModeration
from social_platform.app.admin.services.moderation_guard import ensure_profile_field_allowed
from social_platform.app.admin.services.moderation_service import (
    apply_user_violation,
    release_current_user_restriction,
    release_violation_event,
)
from social_platform.app.core.timezone import local_now
from social_platform.app.db.session import Base
from social_platform.app.domains.content_safety.llm_moderation import parse_llm_decision
from social_platform.app.domains.content_safety.models import UserViolationEvent
from social_platform.app.domains.content_safety.appeal_application import (
    approve_user_appeal,
    create_or_update_appeal,
)
from social_platform.app.domains.user.models import User


@pytest.fixture()
def db_session() -> Iterator[Session]:
    """创建包含完整领域模型的内存数据库会话。"""

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def _seed(db: Session) -> tuple[User, PlatformAdminUser]:
    """写入测试用户和具名管理员。"""

    user = User(username="原用户名", bio="原签名", avatar_url="avatar.png")
    admin = PlatformAdminUser(username="admin", password_hash="hash", is_super_admin=True)
    db.add_all([user, admin])
    db.commit()
    return user, admin


@pytest.mark.parametrize("category", ["publish", "comment", "interaction", "avatar", "username", "bio"])
def test_counted_violation_escalates_one_seven_thirty_days_then_permanent(
    db_session: Session,
    category: str,
) -> None:
    """六类违规分别按 1、7、30 天和永久限制升级。"""

    user, admin = _seed(db_session)
    expected_days = (1, 7, 30)
    for index, days in enumerate(expected_days, start=1):
        before = local_now()
        moderation, event = apply_user_violation(db_session, user.id, category, admin)  # type: ignore[arg-type]
        assert getattr(moderation, f"{category}_violation_count") == index
        assert event.violation_count == index
        assert event.is_permanent is False
        assert event.restriction_until is not None
        assert before + timedelta(days=days) <= event.restriction_until <= local_now() + timedelta(days=days)

    moderation, event = apply_user_violation(db_session, user.id, category, admin)  # type: ignore[arg-type]
    assert getattr(moderation, f"{category}_violation_count") == 4
    assert getattr(moderation, f"{category}_permanently_banned") is True
    assert event.is_permanent is True
    assert event.restriction_until is None


def test_account_violation_removes_profile_without_incrementing_counts(db_session: Session) -> None:
    """账号违规撤下全部资料且不污染六类累计次数。"""

    user, admin = _seed(db_session)
    moderation, _ = apply_user_violation(db_session, user.id, "account", admin, "严重违规")
    db_session.refresh(user)
    assert moderation.account_banned_at is not None
    assert user.username == f"用户_{user.id}"
    assert user.bio is None
    assert user.avatar_url is None
    assert all(
        getattr(moderation, f"{category}_violation_count") == 0
        for category in ("publish", "comment", "interaction", "avatar", "username", "bio")
    )

    released = release_current_user_restriction(db_session, user.id, "account", admin)
    assert released.account_banned_at is None
    assert released.account_ban_reason is None
    assert user.username == f"用户_{user.id}"


def test_content_source_is_counted_only_once(db_session: Session) -> None:
    """同一来源内容重复进入处理链路时复用原事件。"""

    user, admin = _seed(db_session)
    first_moderation, first_event = apply_user_violation(
        db_session,
        user.id,
        "publish",
        admin,
        source_type="post",
        source_id=42,
    )
    second_moderation, second_event = apply_user_violation(
        db_session,
        user.id,
        "publish",
        admin,
        source_type="post",
        source_id=42,
    )
    assert first_event.id == second_event.id
    assert first_moderation.publish_violation_count == 1
    assert second_moderation.publish_violation_count == 1
    assert db_session.query(UserViolationEvent).count() == 1


def test_old_event_release_does_not_clear_newer_restriction_or_count(db_session: Session) -> None:
    """旧处罚申诉通过不会覆盖同类别的新处罚，且解除不回退次数。"""

    user, admin = _seed(db_session)
    _, old_event = apply_user_violation(db_session, user.id, "comment", admin)
    moderation, current_event = apply_user_violation(db_session, user.id, "comment", admin)
    assert release_violation_event(db_session, old_event.id, admin) is False
    db_session.refresh(moderation)
    assert moderation.comment_current_event_id == current_event.id
    assert moderation.comment_violation_count == 2
    assert moderation.comment_banned_until is not None


def test_admin_can_release_one_active_category_without_reducing_count(db_session: Session) -> None:
    """管理员主动解除单项管控后，该类别恢复可用但历史次数保持不变。"""

    user, admin = _seed(db_session)
    apply_user_violation(db_session, user.id, "interaction", admin)
    moderation = release_current_user_restriction(db_session, user.id, "interaction", admin)
    assert moderation.interaction_violation_count == 1
    assert moderation.interaction_banned_until is None
    assert moderation.interaction_permanently_banned is False


def test_old_notification_appeal_reverses_count_without_clearing_newer_violation(
    db_session: Session,
) -> None:
    """旧通知申诉通过会撤销该次计数，但不会清除同类别的新处罚。"""

    user, admin = _seed(db_session)
    _, old_event = apply_user_violation(db_session, user.id, "publish", admin)
    moderation, current_event = apply_user_violation(db_session, user.id, "publish", admin)
    assert old_event.notification_id is not None
    appeal = create_or_update_appeal(db_session, old_event.notification_id, user, "处罚有误")
    approve_user_appeal(db_session, appeal.id, admin)
    db_session.refresh(moderation)
    assert moderation.publish_current_event_id == current_event.id
    assert moderation.publish_violation_count == 1
    assert moderation.publish_banned_until is not None
    assert old_event.violation_count_reversed_at is not None

    release_violation_event(
        db_session,
        old_event.id,
        admin,
        reverse_violation_count=True,
    )
    db_session.refresh(moderation)
    assert moderation.publish_violation_count == 1


def test_profile_guard_checks_only_restricted_field(db_session: Session) -> None:
    """头像处罚只阻止头像修改，不阻止用户名修改。"""

    user, admin = _seed(db_session)
    apply_user_violation(db_session, user.id, "avatar", admin)
    ensure_profile_field_allowed(db_session, user, "username")
    with pytest.raises(HTTPException) as exc_info:
        ensure_profile_field_allowed(db_session, user, "avatar")
    assert exc_info.value.status_code == 403


def test_llm_parser_supports_profile_control_decisions() -> None:
    """LLM 输出可解析用户名和签名局部控制决策。"""

    assert parse_llm_decision("control_username 冒充官方") == ("control_username", "冒充官方")
    assert parse_llm_decision("control_bio：恶意广告") == ("control_bio", "恶意广告")
