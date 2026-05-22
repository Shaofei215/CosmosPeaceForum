# 标准化响应模型
# 定义统一的 API 响应格式，包含分页信息
from typing import TypeVar, Generic, Optional
from pydantic import BaseModel


T = TypeVar("T")


class PaginationInfo(BaseModel):
    """
    分页信息模型
    
    包含分页相关的所有元数据，用于前端实现分页导航
    """
    page: int                    # 当前页码（从1开始）
    page_size: int               # 每页记录数
    total: int                   # 总记录数
    total_pages: int             # 总页数
    has_next: bool               # 是否有下一页
    has_prev: bool               # 是否有上一页


class APIResponse(BaseModel, Generic[T]):
    """
    标准化 API 响应模型
    
    统一的响应格式，包含状态码、消息、数据和分页信息。
    支持泛型，可以包装任意类型的数据。
    
    Attributes:
        code: HTTP 状态码或业务状态码，默认 200
        message: 响应消息，默认 "success"
        data: 响应数据，类型由泛型参数 T 决定
        pagination: 分页信息（可选），列表查询时返回
    
    Example:
        >>> response = APIResponse[List[PostFeedItem]](
        ...     code=200,
        ...     message="success",
        ...     data=[post1, post2],
        ...     pagination=PaginationInfo(
        ...         page=1,
        ...         page_size=20,
        ...         total=100,
        ...         total_pages=5,
        ...         has_next=True,
        ...         has_prev=False
        ...     )
        ... )
    """
    code: int = 200
    message: str = "success"
    data: T
    pagination: Optional[PaginationInfo] = None
