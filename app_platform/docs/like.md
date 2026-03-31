# 点赞系统文档

## 版本信息

| 项目 | 内容 |
|------|------|
| 当前版本 | v1.9.7-Alpha-refactor |
| 更新日期 | 2026.3.30 |

---

## 功能概述

点赞系统支持对帖子和评论进行点赞/取消点赞操作，采用切换模式（Toggle），简化用户交互。

### 核心特性

| 特性 | 说明 |
|------|------|
| Toggle 模式 | 已点赞则取消，未点赞则点赞 |
| 统一数据模型 | 帖子和评论共用 Like 模型 |
| 实时计数 | 点赞后立即更新点赞数 |
| 状态同步 | 支持查询当前用户的点赞状态 |

---

## 数据模型

### Like 模型

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | Primary Key | 点赞记录唯一标识符 |
| user_id | Integer | ForeignKey, Index | 点赞用户 ID |
| post_id | Integer | ForeignKey, Nullable, Index | 点赞的帖子 ID（与 comment_id 二选一） |
| comment_id | Integer | ForeignKey, Nullable, Index | 点赞的评论 ID（与 post_id 二选一） |
| created_at | DateTime | Not Null, Default NOW | 点赞时间 |

### 唯一性约束

```python
__table_args__ = (
    UniqueConstraint('user_id', 'post_id', name='uix_user_post_like'),
    UniqueConstraint('user_id', 'comment_id', name='uix_user_comment_like'),
)
```

- 同一用户对同一帖子只能有一条点赞记录
- 同一用户对同一评论只能有一条点赞记录

---

## API 接口

### 帖子点赞

#### 1. 点赞/取消点赞帖子

**路径**: `POST /api/v1/posts/{post_id}/like`

**认证**: 需要 Bearer Token

**行为**: Toggle 模式 - 已点赞则取消，未点赞则点赞

**响应 (200 OK)**:

```json
{
  "post_id": 1,
  "like_count": 5,
  "is_liked": true
}
```

#### 2. 获取帖子点赞状态

**路径**: `GET /api/v1/posts/{post_id}/like-status`

**认证**: 需要 Bearer Token

**响应 (200 OK)**:

```json
{
  "is_liked": true,
  "like_count": 5
}
```

---

### 评论点赞

#### 3. 点赞/取消点赞评论

**路径**: `POST /api/v1/posts/{post_id}/comments/{comment_id}/like`

**认证**: 需要 Bearer Token

**行为**: Toggle 模式 - 已点赞则取消，未点赞则点赞

**响应 (200 OK)**:

```json
{
  "is_liked": true,
  "like_count": 1
}
```

#### 4. 获取评论点赞状态

**路径**: `GET /api/v1/posts/{post_id}/comments/{comment_id}/like-status`

**认证**: 需要 Bearer Token

**响应 (200 OK)**:

```json
{
  "is_liked": true,
  "like_count": 5
}
```

---

## 实现逻辑

### Toggle 点赞

```python
def toggle_like(db: Session, user_id: int, post_id: int):
    existing_like = db.query(Like).filter(
        Like.user_id == user_id,
        Like.post_id == post_id
    ).first()

    if existing_like:
        db.delete(existing_like)
        is_liked = False
    else:
        new_like = Like(user_id=user_id, post_id=post_id)
        db.add(new_like)
        is_liked = True

    db.commit()

    like_count = db.query(func.count(Like.id)).filter(
        Like.post_id == post_id
    ).scalar()

    return {"is_liked": is_liked, "like_count": like_count}
```

---

## 计数统计

### Post 模型关联计数

点赞数通过 SQLAlchemy `column_property` 或应用层聚合计算：

```python
class Post(Base):
    like_count = column_property(
        select(func.count(Like.id))
        .where(Like.post_id == id)
        .correlate_except(Like)
        .scalar_subquery()
    )
```

### Comment 模型关联计数

评论点赞数同样通过关系聚合计算：

```python
class Comment(Base):
    like_count = column_property(
        select(func.count(Like.id))
        .where(Like.comment_id == id)
        .correlate_except(Like)
        .scalar_subquery()
    )
```

---

## 权限控制

| 操作 | 权限要求 |
|------|----------|
| 点赞/取消点赞 | 需要登录（Bearer Token） |
| 查询点赞状态 | 需要登录（Bearer Token） |

---

## 错误处理

| 错误 | 状态码 | 说明 |
|------|--------|------|
| 帖子不存在 | 404 | post_id 对应的帖子不存在 |
| 评论不存在 | 404 | comment_id 对应的评论不存在 |
| 未授权 | 401 | 未提供有效的认证 Token |

---

## 性能优化

### 数据库索引

| 索引 | 字段 | 用途 |
|------|------|------|
| idx_likes_user_id | user_id | 加速用户点赞列表查询 |
| idx_likes_post_id | post_id | 加速帖子点赞数统计 |
| idx_likes_comment_id | comment_id | 加速评论点赞数统计 |

### 复合索引

| 索引 | 字段 | 用途 |
|------|------|------|
| uix_user_post_like | (user_id, post_id) | 保证唯一性，加速查询 |
| uix_user_comment_like | (user_id, comment_id) | 保证唯一性，加速查询 |

---

## 与其他模块的关系

```
┌─────────────────────────────────────────────────────┐
│                    点赞系统                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  支持点赞:                                          │
│  ├── Posts (帖子)                                   │
│  └── Comments (评论)                               │
│                                                     │
│  依赖模块:                                          │
│  ├── Users (用户认证)                               │
│  └── Posts/Comments (被点赞对象)                    │
│                                                     │
│  被依赖模块:                                        │
│  └── Feed (信息流需要显示点赞状态)                   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

*文档版本：v1.9.7-Alpha-refactor | 更新日期：2026.3.30*
