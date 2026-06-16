"""热榜领域公开 API DTO。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class HotTopicResponse(BaseModel):
    """公开热榜条目响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    search_query: str
    summary: Optional[str] = None
    source: str
    status: str
    rank: int
    generation_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
