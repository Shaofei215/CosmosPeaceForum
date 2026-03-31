# 信息流系统文档

## 版本信息

| 项目 | 内容 |
|------|------|
| 当前版本 | v1.9.7-Alpha-refactor |
| 更新日期 | 2026.3.30 |

---

## 功能概述

信息流系统为用户提供统一的内容聚合视图，支持全局信息流和用户专属信息流两种模式。

### 信息流类型

| 类型 | 说明 |
|------|------|
| 全局信息流 | 聚合所有用户的公开帖子，按时间倒序排列 |
| 用户帖子流 | 指定用户发布的帖子列表 |

---

## 数据聚合

### 信息流条目字段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | integer | 帖子 ID |
| title | string | 帖子标题（可为空） |
| content | string | 帖子内容 |
| created_at | datetime | 创建时间 |
| author_id | integer | 作者用户 ID |
| author_name | string | 作者用户名 |
| author_avatar | string | 作者头像 URL |
| like_count | integer | 点赞数 |
| comment_count | integer | 评论数 |
| is_liked | boolean | 当前用户是否已点赞（需认证） |

---

## API 接口

### 1. 获取全局信息流

**路径**: `GET /api/v1/feeds/feed/all`

**认证**: 不需要（传入 `current_user_id` 可返回点赞状态）

**查询参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | integer | 否 | 1 | 页码，从 1 开始 |
| page_size | integer | 否 | 20 | 每页记录数，最大 100 |
| current_user_id | integer | 否 | null | 当前用户 ID（用于返回点赞状态） |

**响应 (200 OK)**:

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "id": 1,
      "title": "今天天气真好",
      "content": "适合出去走走！",
      "created_at": "2026-03-17T10:00:00",
      "author_id": 1,
      "author_name": "三月七",
      "author_avatar": "https://example.com/avatar.jpg",
      "like_count": 15,
      "comment_count": 8,
      "is_liked": true
    },
    {
      "id": 2,
      "title": "空间站的日常",
      "content": "今天的黑塔又在摸鱼...",
      "created_at": "2026-03-17T09:00:00",
      "author_id": 2,
      "author_name": "黑塔",
      "author_avatar": "https://example.com/hat.jpg",
      "like_count": 23,
      "comment_count": 12,
      "is_liked": false
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5,
    "has_next": true,
    "has_prev": false
  }
}
```

---

### 2. 获取用户帖子流

**路径**: `GET /api/v1/feeds/feed/user/{user_id}`

**认证**: 不需要

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | integer | 是 | 用户 ID |

**查询参数**: 同全局信息流

**响应格式**: 同全局信息流

---

## 分页机制

### 分页参数

| 参数 | 默认值 | 最大值 | 说明 |
|------|--------|--------|------|
| page | 1 | - | 页码，从 1 开始 |
| page_size | 20 | 100 | 每页记录数 |

### 分页响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| page | integer | 当前页码 |
| page_size | integer | 每页记录数 |
| total | integer | 总记录数 |
| total_pages | integer | 总页数 |
| has_next | boolean | 是否有下一页 |
| has_prev | boolean | 是否有上一页 |

### 分页计算公式

```python
total_pages = ceil(total / page_size)
has_next = page < total_pages
has_prev = page > 1
offset = (page - 1) * page_size
```

---

## 实现逻辑

### 全局信息流查询

```python
def get_global_feed(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    current_user_id: int = None
):
    offset = (page - 1) * page_size

    posts = db.query(Post).order_by(
        Post.created_at.desc()
    ).offset(offset).limit(page_size).all()

    total = db.query(func.count(Post.id)).scalar()

    items = []
    for post in posts:
        item = {
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "created_at": post.created_at,
            "author_id": post.author_id,
            "author_name": post.author.username,
            "author_avatar": post.author.avatar_url,
            "like_count": post.like_count,
            "comment_count": post.comment_count,
        }
        if current_user_id:
            item["is_liked"] = db.query(Like).filter(
                Like.post_id == post.id,
                Like.user_id == current_user_id
            ).first() is not None
        items.append(item)

    return {
        "code": 200,
        "message": "success",
        "data": items,
        "pagination": {...}
    }
```

---

## 性能优化

### 数据库索引

| 索引 | 字段 | 用途 |
|------|------|------|
| idx_posts_created_at | created_at | 加速时间排序查询 |
| idx_posts_author_id | author_id | 加速用户帖子查询 |

### N+1 问题

信息流需要关联查询用户表获取作者信息，建议使用 **SQLAlchemy joinedload** 预加载：

```python
from sqlalchemy.orm import joinedload

posts = db.query(Post).options(
    joinedload(Post.author)
).order_by(
    Post.created_at.desc()
).offset(offset).limit(page_size).all()
```

---

## 与其他模块的关系

```
┌─────────────────────────────────────────────┐
│              信息流 (Feed)                  │
├─────────────────────────────────────────────┤
│                                             │
│  依赖数据:                                   │
│  ├── Posts (帖子列表)                        │
│  ├── Users (作者信息)                        │
│  └── Likes (点赞状态)                        │
│                                             │
│  不直接操作:                                 │
│  ├── Comments (评论数通过关系获取)            │
│  └── 点赞/评论本身                           │
│                                             │
└─────────────────────────────────────────────┘
```

---

*文档版本：v1.9.7-Alpha-refactor | 更新日期：2026.3.30*
