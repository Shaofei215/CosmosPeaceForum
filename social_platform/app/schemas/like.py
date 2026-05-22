# 点赞数据验证模型（Pydantic Schemas）
# 定义点赞数据的请求和响应格式
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class LikeToggleResponse(BaseModel):
    """
    点赞操作响应模型
    用于点赞/取消点赞操作的 API 响应
    
    Attributes:
        post_id: 帖子 ID
        like_count: 当前点赞总数
        is_liked: 当前用户是否已点赞该帖子
    
    Note:
        - is_liked 为 True 表示点赞成功
        - is_liked 为 False 表示取消点赞成功
    """
    # 帖子 ID
    post_id: int
    
    # 当前点赞总数
    like_count: int
    
    # 当前用户是否已点赞该帖子
    is_liked: bool


class LikeStatusMixin(BaseModel):
    """
    点赞状态混入模型
    用于混入帖子详情响应，增加 is_liked 字段
    
    Attributes:
        is_liked_by_current_user: 当前用户是否已点赞该帖子
    
    Note:
        使用继承方式将此 mixin 混入到 PostResponse 中
    """
    # 当前用户是否已点赞该帖子
    is_liked_by_current_user: bool = False


class LikeCountResponse(BaseModel):
    """
    点赞数响应模型
    仅返回帖子的点赞数量
    
    Attributes:
        post_id: 帖子 ID
        like_count: 点赞总数
    """
    # 帖子 ID
    post_id: int
    
    # 点赞总数
    like_count: int
