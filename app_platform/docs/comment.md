# 评论系统文档

## 版本信息

| 项目 | 内容 |
|------|------|
| 当前版本 | v1.9.7-Alpha-refactor |
| 更新日期 | 2026.3.30 |

---

## 功能概述

评论系统支持**无限层级嵌套回复**，允许用户在帖子下进行多层次的讨论。

### 核心特性

| 特性 | 说明 |
|------|------|
| 无限层级嵌套 | 支持任意深度的回复嵌套 |
| 评论树结构 | 返回树形结构的评论列表 |
| 点赞功能 | 支持评论点赞和取消点赞 |
| 所有权验证 | 只有评论作者可以删除自己的评论 |

---

## 数据模型

### Comment 模型

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | Primary Key | 评论唯一标识符 |
| post_id | Integer | ForeignKey, Index | 所属帖子 ID |
| owner_id | Integer | ForeignKey, Index | 评论作者 ID |
| parent_id | Integer | ForeignKey, Nullable, Index | 父评论 ID，NULL 表示一级评论 |
| content | Text | Not Null | 评论内容 |
| created_at | DateTime | Not Null, Default NOW | 创建时间 |
| updated_at | DateTime | Not Null | 更新时间 |

### 关系定义

```python
class Comment(Base):
    post = relationship("Post", back_populates="comments")
    owner = relationship("User")
    parent = relationship("Comment", remote_side=[id], back_populates="children")
    children = relationship("Comment", back_populates="parent", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="comment", cascade="all, delete-orphan")
```

---

## API 接口

### 1. 创建评论/回复

**路径**: `POST /api/v1/posts/{post_id}/comments`

**认证**: 需要 Bearer Token

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| content | string | 是 | 评论内容，至少 1 个字符 |
| parent_id | integer | 否 | 父评论 ID，为空表示一级评论 |

**响应 (201 Created)**:

```json
{
  "id": 1,
  "post_id": 1,
  "owner_id": 123,
  "parent_id": null,
  "content": "这是一条评论",
  "like_count": 0,
  "reply_count": 0,
  "created_at": "2026-03-17T07:00:00",
  "is_liked": false,
  "owner": {
    "id": 123,
    "username": "测试用户",
    "bio": "用户简介",
    "avatar_url": "https://example.com/avatar.jpg",
    "created_at": "2026-03-17T06:00:00"
  }
}
```

---

### 2. 获取评论树

**路径**: `GET /api/v1/posts/{post_id}/comments`

**认证**: 不需要

**查询参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| user_id | integer | 否 | null | 当前用户 ID（用于返回点赞状态） |
| skip | integer | 否 | 0 | 跳过前 N 条一级评论 |
| limit | integer | 否 | 20 | 返回一级评论数量，最大 100 |

**响应 (200 OK)**:

```json
{
  "items": [
    {
      "id": 1,
      "post_id": 1,
      "owner_id": 123,
      "parent_id": null,
      "content": "一级评论",
      "like_count": 5,
      "reply_count": 2,
      "created_at": "2026-03-17T07:00:00",
      "is_liked": true,
      "owner": {...},
      "children": [
        {
          "id": 2,
          "post_id": 1,
          "owner_id": 456,
          "parent_id": 1,
          "content": "回复 A",
          "like_count": 1,
          "reply_count": 1,
          "created_at": "2026-03-17T07:01:00",
          "is_liked": false,
          "owner": {...},
          "children": [
            {
              "id": 3,
              "parent_id": 2,
              "content": "深层回复",
              "children": []
            }
          ]
        }
      ]
    }
  ],
  "total": 3,
  "skip": 0,
  "limit": 20
}
```

---

### 3. 获取评论详情

**路径**: `GET /api/v1/posts/{post_id}/comments/{comment_id}`

**认证**: 不需要

**响应 (200 OK)**:

```json
{
  "id": 1,
  "post_id": 1,
  "owner_id": 123,
  "parent_id": null,
  "content": "评论内容",
  "like_count": 5,
  "reply_count": 2,
  "created_at": "2026-03-17T07:00:00",
  "is_liked": true,
  "owner": {...}
}
```

---

### 4. 删除评论

**路径**: `DELETE /api/v1/posts/{post_id}/comments/{comment_id}`

**认证**: 需要 Bearer Token（仅评论作者）

**行为说明**:

- 删除一级评论时，**级联删除**所有子评论
- 删除子评论时，只删除该评论本身

**响应**: `204 No Content`

---

### 5. 评论点赞/取消点赞

**路径**: `POST /api/v1/posts/{post_id}/comments/{comment_id}/like`

**认证**: 需要 Bearer Token

**响应 (200 OK)**:

```json
{
  "is_liked": true,
  "like_count": 1
}
```

---

### 6. 获取评论点赞状态

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

## 实现细节

### 评论树构建逻辑

```python
def get_comment_tree(post_id: int, db: Session, skip: int = 0, limit: int = 20):
    root_comments = db.query(Comment).filter(
        Comment.post_id == post_id,
        Comment.parent_id == None
    ).offset(skip).limit(limit).all()

    def build_tree(comment: Comment) -> dict:
        children = db.query(Comment).filter(
            Comment.parent_id == comment.id
        ).all()
        return {
            **comment.to_dict(),
            "children": [build_tree(c) for c in children]
        }

    return [build_tree(c) for c in root_comments]
```

### 计数统计逻辑

| 计数 | 统计范围 |
|------|----------|
| `like_count` | 该评论的直接点赞数 |
| `reply_count` | 该评论下的**所有**回复总数（包括嵌套回复） |

### 权限控制

```python
def delete_comment(comment_id: int, current_user: User, db: Session):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    if comment.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除此评论")
    db.delete(comment)
    db.commit()
```

---

## 性能考虑

### 嵌套层级限制

建议在产品层面限制评论嵌套层级（通常 3-5 层），以避免：

- 数据库查询过于复杂
- 前端渲染性能问题
- 用户体验下降

### 数据库索引

| 索引 | 用途 |
|------|------|
| `post_id + parent_id` | 加速评论树查询 |
| `owner_id` | 加速用户评论列表查询 |

---

## 错误处理

| 错误 | 状态码 | 说明 |
|------|--------|------|
| 帖子不存在 | 404 | post_id 对应的帖子不存在 |
| 评论不存在 | 404 | comment_id 对应的评论不存在 |
| 父评论不存在 | 404 | 指定的 parent_id 不存在 |
| 无权删除 | 403 | 非评论作者尝试删除 |

---

*文档版本：v1.9.7-Alpha-refactor | 更新日期：2026.3.30*
