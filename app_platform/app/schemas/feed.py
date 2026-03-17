# Feed 信息流数据验证模型
# 定义信息流相关的请求和响应格式
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class PostFeedItem(BaseModel):
    """
    信息流帖子项
    
    包含展示帖子所需的完整信息，用于信息流展示。
    前端可直接使用此数据结构渲染帖子卡片。
    
    Attributes:
        id: 帖子ID
        title: 帖子标题（可选）
        content: 帖子内容
        created_at: 创建时间
        author_id: 作者ID
        author_name: 作者用户名
        author_avatar: 作者头像（可选）
        like_count: 点赞数
        comment_count: 评论总数
        is_liked: 当前用户是否已点赞
    """
    # 基础字段
    id: int
    title: Optional[str] = None
    content: str
    created_at: datetime
    
    # 作者信息
    author_id: int
    author_name: str
    author_avatar: Optional[str] = None
    
    # 统计字段
    like_count: int = 0
    comment_count: int = 0
    
    # 状态字段
    is_liked: bool = False
    
    class Config:
        from_attributes = True
