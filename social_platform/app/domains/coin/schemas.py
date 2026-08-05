"""硬币领域 API 请求与响应模型。"""

from pydantic import BaseModel


class PostCoinResponse(BaseModel):
    """投币结果与当前用户余额。"""

    post_id: int
    coin_count: int
    is_coined: bool
    coin_balance: int
    created_by_agent: bool = False


class PostCoinStatusResponse(BaseModel):
    """当前用户对帖子的投币状态。"""

    post_id: int
    coin_count: int
    is_coined: bool
    coin_balance: int
