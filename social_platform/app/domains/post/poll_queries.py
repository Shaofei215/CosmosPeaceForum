"""帖子投票读侧查询。

本模块只负责把投票选项、票数和当前用户选择组装成 API 响应模型，供帖子详情、
信息流和 Agent 工具复用；不提交事务，也不修改数据库状态。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from social_platform.app.domains.post.models import PollOption, PollVote
from social_platform.app.domains.post.schemas import PollOptionResponse, PollResponse


def get_poll_response(db: Session, post_id: int, current_user_id: int | None) -> PollResponse | None:
    """读取单个帖子的投票统计。

    Args:
        db: 当前数据库会话。
        post_id: 待读取投票的帖子 ID。
        current_user_id: 当前用户 ID；匿名访问时为 ``None``。

    Returns:
        PollResponse | None: 帖子没有投票时返回 ``None``，否则返回选项统计与当前用户选择。
    """

    poll_map = build_poll_response_map(db, [post_id], current_user_id)
    return poll_map.get(post_id)


def build_poll_response_map(
    db: Session,
    post_ids: list[int],
    current_user_id: int | None,
) -> dict[int, PollResponse]:
    """批量读取帖子投票统计。

    Args:
        db: 当前数据库会话。
        post_ids: 待读取投票的帖子 ID 列表。
        current_user_id: 当前用户 ID；匿名访问时为 ``None``。

    Returns:
        dict[int, PollResponse]: 帖子 ID 到投票响应的映射；无投票帖子不会出现在结果中。
    """

    if not post_ids:
        return {}

    options = (
        db.query(PollOption)
        .filter(PollOption.post_id.in_(post_ids))
        .order_by(PollOption.post_id.asc(), PollOption.position.asc())
        .all()
    )
    if not options:
        return {}

    selected_option_by_post: dict[int, int] = {}
    if current_user_id:
        votes = (
            db.query(PollVote.post_id, PollVote.option_id)
            .filter(PollVote.post_id.in_(post_ids), PollVote.user_id == current_user_id)
            .all()
        )
        selected_option_by_post = {post_id: option_id for post_id, option_id in votes}

    grouped_options: dict[int, list[PollOption]] = {}
    for option in options:
        grouped_options.setdefault(option.post_id, []).append(option)

    poll_map: dict[int, PollResponse] = {}
    for post_id, post_options in grouped_options.items():
        total_votes = sum(option.vote_count for option in post_options)
        selected_option_id = selected_option_by_post.get(post_id)
        poll_map[post_id] = PollResponse(
            post_id=post_id,
            total_votes=total_votes,
            has_voted=selected_option_id is not None,
            selected_option_id=selected_option_id,
            options=[
                PollOptionResponse(
                    id=option.id,
                    text=option.text,
                    position=option.position,
                    vote_count=option.vote_count,
                    percentage=round(option.vote_count * 100 / total_votes, 1)
                    if total_votes
                    else 0,
                )
                for option in post_options
            ],
        )

    return poll_map
