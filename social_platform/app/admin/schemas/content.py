from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ContentItemResponse(BaseModel):
    id: int
    type: str
    post_id: Optional[int] = None
    author_id: int
    author_username: Optional[str]
    title: Optional[str] = None
    content: str
    created_at: datetime
    like_count: int
    comment_count: Optional[int] = None
    reply_count: Optional[int] = None

class ContentReportReasonResponse(BaseModel):
    reason: str
    count: int


class ReportedContentItemResponse(ContentItemResponse):
    report_count: int
    report_reasons: list[ContentReportReasonResponse]
    last_reported_at: datetime
