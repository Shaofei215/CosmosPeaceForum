"""帖子热度计算行为测试。

本模块验证互动压缩与时间衰减的关键产品语义，防止推荐排序调整时重新引入
高互动旧帖长期垄断候选池的问题。
"""

import math
from datetime import datetime, timedelta

import pytest

from social_platform.app.domains.heat.application import calculate_post_heat_score
from social_platform.app.domains.post.models import Post


def _post(
    *,
    created_at: datetime,
    like_count: int = 0,
    comment_count: int = 0,
    repost_count: int = 0,
) -> Post:
    """构造热度计算测试使用的帖子。

    Args:
        created_at: 帖子创建时间。
        like_count: 点赞数。
        comment_count: 评论与回复总数。
        repost_count: 转发数。

    Returns:
        Post: 不依赖数据库会话的帖子模型实例。
    """

    return Post(
        author_id=1,
        content="测试帖子",
        created_at=created_at,
        like_count=like_count,
        comment_count=comment_count,
        repost_count=repost_count,
    )


def test_post_heat_score_uses_compressed_interactions_and_faster_decay() -> None:
    """热度应使用压缩后的互动质量和 1.6 次幂时间衰减。"""

    now = datetime(2026, 7, 20, 12, 0, 0)
    post = _post(
        created_at=now - timedelta(hours=18),
        like_count=9,
        comment_count=4,
        repost_count=2,
    )

    score = calculate_post_heat_score(post, now)

    expected = math.sqrt(1 + 9 + 2 * 4 + 4 * 2) / (18 + 6) ** 1.6
    assert score == pytest.approx(expected)


def test_fresh_post_can_outrank_high_interaction_old_post() -> None:
    """两日内的零互动帖子应能获得高于十日高互动帖的探索机会。"""

    now = datetime(2026, 7, 20, 12, 0, 0)
    fresh_post = _post(created_at=now - timedelta(days=2))
    old_post = _post(
        created_at=now - timedelta(days=10),
        like_count=40,
        comment_count=40,
    )

    assert calculate_post_heat_score(fresh_post, now) > calculate_post_heat_score(old_post, now)


def test_more_interactions_still_raise_heat_at_the_same_age() -> None:
    """同龄帖子之间仍应由更多有效互动获得更高热度。"""

    now = datetime(2026, 7, 20, 12, 0, 0)
    quiet_post = _post(created_at=now - timedelta(hours=12), like_count=1)
    active_post = _post(
        created_at=now - timedelta(hours=12),
        like_count=5,
        comment_count=3,
        repost_count=1,
    )

    assert calculate_post_heat_score(active_post, now) > calculate_post_heat_score(quiet_post, now)
