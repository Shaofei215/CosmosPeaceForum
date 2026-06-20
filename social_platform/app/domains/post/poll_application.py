"""帖子投票写侧应用服务。

本模块承接投票选项创建、投票参数校验和用户投票事务。帖子创建流程只调用
``create_poll_options`` 完成同事务选项写入；HTTP 路由通过 ``vote_poll`` 处理用户选择。
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from social_platform.app.admin.services.moderation_guard import ensure_action_allowed
from social_platform.app.domains.post.models import PollOption, PollVote, Post
from social_platform.app.domains.user.models import User
from social_platform.app.shared.unit_of_work import commit_session


class InvalidPollError(Exception):
    """投票参数非法异常。"""

    def __init__(self, message: str) -> None:
        """初始化投票参数非法异常。

        Args:
            message: 面向调用方的校验失败原因。
        """

        super().__init__(message)


class PollAlreadyVotedError(Exception):
    """用户已对帖子投票异常。"""

    def __init__(self) -> None:
        """初始化重复投票异常。"""

        super().__init__("已对该投票做出选择，不能重复投票")


class PollOptionNotFoundError(Exception):
    """投票选项不存在异常。

    Args:
        post_id: 投票所属帖子 ID。
        option_id: 用户选择的选项 ID。
    """

    def __init__(self, post_id: int, option_id: int) -> None:
        """初始化投票选项不存在异常。

        Args:
            post_id: 投票所属帖子 ID。
            option_id: 用户选择的选项 ID。
        """

        self.post_id = post_id
        self.option_id = option_id
        super().__init__("投票选项不存在")


class PollPostNotFoundError(Exception):
    """投票所属帖子不存在异常。

    Args:
        post_id: 不存在或不可见的帖子 ID。
    """

    def __init__(self, post_id: int) -> None:
        """初始化投票帖子不存在异常。

        Args:
            post_id: 不存在或不可见的帖子 ID。
        """

        self.post_id = post_id
        super().__init__("帖子不存在")


def create_poll_options(
    db: Session,
    post_id: int,
    post_type: str,
    options: list[str] | None,
) -> list[PollOption]:
    """在帖子创建事务内写入投票选项。

    Args:
        db: 当前数据库会话。
        post_id: 已创建并 flush 的帖子 ID。
        post_type: 帖子类型，只有 ``post`` 可以附带投票。
        options: 外部传入的选项文本列表。

    Returns:
        list[PollOption]: 已加入会话但尚未提交的投票选项模型列表。

    Raises:
        InvalidPollError: 当选项数量、长度、重复性或帖子类型不满足规则时抛出。
    """

    normalized_options = normalize_poll_options(options)
    if not normalized_options:
        return []
    if post_type != "post":
        raise InvalidPollError("只有普通帖子可以发起投票")

    poll_options = [
        PollOption(post_id=post_id, text=option_text, position=index)
        for index, option_text in enumerate(normalized_options)
    ]
    db.add_all(poll_options)
    return poll_options


def normalize_poll_options(options: list[str] | None) -> list[str]:
    """清洗并校验创建帖子时传入的投票选项。

    Args:
        options: 外部传入的选项文本列表。

    Returns:
        list[str]: 去除首尾空白后的投票选项；未传入时返回空列表。

    Raises:
        InvalidPollError: 当选项数量、长度或重复性不满足规则时抛出。
    """

    if options is None:
        return []

    normalized = [(option or "").strip() for option in options]
    if any(not option for option in normalized):
        raise InvalidPollError("投票选项不能为空")
    if len(normalized) < 2 or len(normalized) > 5:
        raise InvalidPollError("投票选项数量必须为 2 到 5 个")
    if any(len(option) > 20 for option in normalized):
        raise InvalidPollError("每个投票选项最多 20 个字")
    if len(set(normalized)) != len(normalized):
        raise InvalidPollError("投票选项不能重复")
    return normalized


def vote_poll(db: Session, current_user: User, post_id: int, option_id: int) -> None:
    """为帖子投票并更新选项统计。

    Args:
        db: 当前数据库会话。
        current_user: 当前登录用户。
        post_id: 投票所属帖子 ID。
        option_id: 用户选择的选项 ID。

    Raises:
        PollPostNotFoundError: 当帖子不存在或不可见时抛出。
        PollOptionNotFoundError: 当帖子没有该选项时抛出。
        PollAlreadyVotedError: 当用户已投过票时抛出。
    """

    ensure_action_allowed(db, current_user, "interaction")
    post_exists = db.query(Post.id).filter(
        Post.id == post_id,
        Post.moderation_status == "active",
    ).first()
    if not post_exists:
        raise PollPostNotFoundError(post_id)

    option = db.query(PollOption).filter(
        PollOption.id == option_id,
        PollOption.post_id == post_id,
    ).first()
    if option is None:
        raise PollOptionNotFoundError(post_id, option_id)

    vote = PollVote(post_id=post_id, option_id=option_id, user_id=current_user.id)
    db.add(vote)
    option.vote_count += 1
    try:
        commit_session(db)
    except IntegrityError as exc:
        db.rollback()
        raise PollAlreadyVotedError() from exc
