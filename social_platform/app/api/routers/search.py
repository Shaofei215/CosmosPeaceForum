from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from social_platform.app.api.deps import get_current_user_optional, get_db
from social_platform.app.domains.search import application as search_service
from social_platform.app.domains.search.schemas import SearchType
from social_platform.app.domains.user.models import User


router = APIRouter()


@router.get(
    "",
    summary="搜索内容或用户",
    description="使用 Tantivy BM25 + jieba 分词搜索帖子/文章标题正文或用户名。",
)
def search(
    type: SearchType = Query(..., description="搜索类型：content（帖子/文章标题正文）或 user（用户名）"),
    q: str = Query(..., min_length=1, max_length=100, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=50, description="每页记录数，最大50"),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    try:
        if type == "content":
            return search_service.search_content(
                db=db,
                query=q,
                page=page,
                page_size=page_size,
                current_user_id=current_user.id if current_user else None,
            )
        return search_service.search_users(
            db=db,
            query=q,
            page=page,
            page_size=page_size,
            current_user_id=current_user.id if current_user else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(exc)}")
