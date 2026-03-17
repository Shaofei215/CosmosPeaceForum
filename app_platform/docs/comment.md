# 评论功能开发文档

## 版本信息

- **时间**: 2026.3.17 7:00
- **版本**: Alpha-v1.4.0-feat: 新增评论功能
- **作者**: Herta-Tree 开发团队

---

## 功能概述

本次更新为 Herta-Tree 社交平台后端新增了完整的**评论与回复功能**，支持无限层级嵌套回复、评论点赞、以及三重冗余计数机制，确保高并发场景下的数据一致性和查询性能。

### 核心特性

- ✅ 评论/回复创建（支持无限层级嵌套）
- ✅ 评论点赞/取消点赞切换机制
- ✅ 三重冗余计数（like_count, reply_count, comment_count）
- ✅ 事务保证多表联动一致性
- ✅ 递归更新祖先回复计数
- ✅ 评论树查询（批量加载优化）
- ✅ 完整的错误处理机制

---

## 更改的文件

### 1. 新增文件

#### `app/models/comment.py`
**更改说明**: 新建评论数据库模型
- 定义 `Comment` 模型类，支持无限层级回复
  - `id`: 自增主键
  - `post_id`: 关联帖子ID（外键）
  - `owner_id`: 评论发布者ID（外键）
  - `parent_id`: 父评论ID（自关联，可为空）
  - `content`: 评论内容
  - `like_count`: 冗余点赞数（默认0）
  - `reply_count`: 全量回复数（默认0，统计所有子孙后代）
  - `created_at`: 创建时间
- 定义 `CommentLike` 模型类，记录评论点赞关系
  - 使用 `(user_id, comment_id)` 复合主键确保唯一性
  - 添加外键约束（`ondelete="CASCADE"`）保证参照完整性
  - 创建索引优化查询性能（`idx_comment_likes_comment_id`, `idx_comment_likes_user_id`）
- 建立与 `User`、`Post`、`Comment` 的双向关联关系
- 使用 `remote_side=[id]` 实现自关联支持无限层级

#### `app/schemas/comment.py`
**更改说明**: 新建评论相关 Pydantic Schemas
- `CommentCreate`: 创建评论请求模型（content, parent_id可选）
- `CommentUpdate`: 更新评论请求模型
- `CommentResponse`: 单条评论响应模型（含 like_count, reply_count, is_liked, owner信息）
- `CommentTreeResponse`: 评论树响应模型（递归结构，支持无限层级 children）
- `CommentLikeToggleResponse`: 点赞操作响应模型（is_liked, like_count）
- `CommentListResponse`: 评论列表响应模型（分页数据）

#### `app/services/comment_service.py`
**更改说明**: 新建评论业务逻辑层
- 自定义异常类：
  - `PostNotFoundError`: 帖子不存在异常
  - `CommentNotFoundError`: 评论不存在异常
  - `ParentCommentNotFoundError`: 父评论不存在异常
  - `ParentCommentMismatchError`: 父评论与帖子不匹配异常
- 核心函数：
  - `create_comment()`: 创建评论/回复（事务内联动更新计数）
  - `toggle_like()`: 点赞/取消切换（事务保证双写一致性）
  - `get_like_status()`: 获取点赞状态
  - `get_comment_tree()`: 获取评论树（批量加载+递归组装）
  - `get_comment_by_id()`: 根据ID获取评论详情
  - `delete_comment()`: 删除评论（级联更新计数）

#### `app/api/routers/comment.py`
**更改说明**: 新建评论路由控制器
- `POST /posts/{post_id}/comments`: 创建评论/回复（201 Created）
- `GET /posts/{post_id}/comments`: 获取评论树（200 OK）
- `POST /posts/{post_id}/comments/{comment_id}/like`: 点赞/取消点赞（200 OK）
- `GET /posts/{post_id}/comments/{comment_id}/like-status`: 获取点赞状态（200 OK）
- `GET /posts/{post_id}/comments/{comment_id}`: 获取评论详情（200 OK）
- `DELETE /posts/{post_id}/comments/{comment_id}`: 删除评论（204 No Content）

#### `app/models/__init__.py`
**更改说明**: 新建模型包初始化文件
- 导入所有模型以确保 SQLAlchemy 正确注册关系
- 解决模型间循环引用问题

### 2. 修改文件

#### `app/models/post.py`
**更改说明**: 扩展帖子模型
- 新增 `comment_count` 字段（Integer，默认 0，非空）
- 新增 `comments` 关联关系（与 `Comment` 模型双向关联，级联删除）

#### `app/models/user.py`
**更改说明**: 扩展用户模型
- 新增 `comments` 关联关系（与 `Comment` 模型双向关联，级联删除）
- 新增 `comment_likes` 关联关系（与 `CommentLike` 模型双向关联）

#### `app/main.py`
**更改说明**: 注册评论路由和模型导入
- 导入所有模型以确保 SQLAlchemy 正确注册关系
- 注册路由：`app.include_router(comment.router, prefix=f"{settings.API_V1_PREFIX}/posts", tags=["comments"])`

---

## API 接口文档

### 评论相关接口

| 接口 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/v1/posts/{post_id}/comments` | POST | `user_id` (query, 必填), `content`, `parent_id` (可选) | `CommentResponse` |
| `/api/v1/posts/{post_id}/comments` | GET | `user_id` (query, 可选), `skip`, `limit` | `CommentListResponse` |
| `/api/v1/posts/{post_id}/comments/{comment_id}/like` | POST | `user_id` (query, 必填) | `CommentLikeToggleResponse` |
| `/api/v1/posts/{post_id}/comments/{comment_id}/like-status` | GET | `user_id` (query, 必填) | `{is_liked, like_count}` |
| `/api/v1/posts/{post_id}/comments/{comment_id}` | GET | `user_id` (query, 可选) | `CommentResponse` |
| `/api/v1/posts/{post_id}/comments/{comment_id}` | DELETE | `user_id` (query, 必填) | 204 No Content |

### 响应示例

#### 创建评论
```json
{
  "id": 1,
  "post_id": 1,
  "owner_id": 123,
  "parent_id": null,
  "content": "这是一级评论",
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

#### 创建回复
```json
{
  "id": 2,
  "post_id": 1,
  "owner_id": 456,
  "parent_id": 1,
  "content": "这是回复",
  "like_count": 0,
  "reply_count": 0,
  "created_at": "2026-03-17T07:01:00",
  "is_liked": false,
  "owner": {...}
}
```

#### 评论树响应
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
          "content": "回复B",
          "like_count": 1,
          "reply_count": 1,
          "created_at": "2026-03-17T07:01:00",
          "is_liked": false,
          "owner": {...},
          "children": [
            {
              "id": 3,
              "post_id": 1,
              "owner_id": 789,
              "parent_id": 2,
              "content": "回复C",
              "like_count": 0,
              "reply_count": 0,
              "created_at": "2026-03-17T07:02:00",
              "is_liked": false,
              "owner": {...},
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

#### 点赞/取消点赞
```json
{
  "is_liked": true,
  "like_count": 10
}
```

---

## 数据库设计

### 新增表

#### `comments` 表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK, Auto | 评论唯一ID |
| post_id | Integer | FK(posts.id), Index, NonNull | 关联帖子ID |
| owner_id | Integer | FK(users.id), Index, NonNull | 评论发布者ID |
| parent_id | Integer | FK(comments.id), Index, Nullable | 父评论ID（自关联） |
| content | Text | NonNull | 评论内容 |
| like_count | Integer | Default 0, NonNull | 点赞计数（冗余） |
| reply_count | Integer | Default 0, NonNull | 全量回复数（冗余） |
| created_at | DateTime | Default UTC | 创建时间 |

**索引**:
- 主键: `id`
- `idx_comments_post_id`: 加速帖子评论查询
- `idx_comments_owner_id`: 加速用户评论查询
- `idx_comments_parent_id`: 加速父评论查询

#### `comment_likes` 表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| user_id | Integer | FK(users.id), PK | 点赞用户ID |
| comment_id | Integer | FK(comments.id), PK | 被赞评论ID |
| created_at | DateTime | Default UTC | 点赞时间 |

**索引**:
- 复合主键: `(user_id, comment_id)`
- `idx_comment_likes_comment_id`: 加速评论点赞查询
- `idx_comment_likes_user_id`: 加速用户点赞查询

### 扩展表

#### `posts` 表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| comment_count | Integer | Default 0, NonNull | 评论总数（冗余存储） |

---

## 业务逻辑说明

### 创建评论/回复流程

1. **校验阶段**
   - 检查帖子是否存在（不存在则抛出 `PostNotFoundError`）
   - 如果指定了 `parent_id`，检查父评论是否存在（不存在则抛出 `ParentCommentNotFoundError`）
   - 检查父评论是否属于同一帖子（不匹配则抛出 `ParentCommentMismatchError`）

2. **执行创建**（在事务中）
   - `INSERT INTO comments` 创建新评论
   - `UPDATE posts SET comment_count = comment_count + 1` 更新帖子计数
   - 如果 `parent_id` 不为空，**循环更新所有祖先**的 `reply_count`

3. **提交事务**
   - 任何一步失败则回滚整个事务

### 递归更新祖先 reply_count 算法

```python
current_id = parent_id
while current_id is not None:
    ancestor = db.query(Comment).filter(Comment.id == current_id).first()
    if ancestor:
        ancestor.reply_count = ancestor.reply_count + 1
        current_id = ancestor.parent_id  # 继续向上追溯
    else:
        break
```

### 评论点赞流程

与帖子点赞逻辑一致：
1. 检查评论是否存在
2. 检查当前点赞状态
3. 执行切换操作（在事务中）
4. 提交事务

### 获取评论树流程

1. **查询一级评论**（`parent_id IS NULL`）
   - 使用 `joinedload` 预加载 `owner` 信息
   - 支持分页（`skip`, `limit`）

2. **批量查询所有回复**
   - 一次性查询该帖子下所有非一级评论
   - 使用字典按 `parent_id` 分组

3. **递归组装树结构**
   - 为每个评论附加 `children` 列表
   - 递归处理嵌套回复

4. **注入点赞状态**（如果提供了 `user_id`）
   - 批量查询用户的所有点赞记录
   - 递归设置每个评论的 `is_liked` 属性

### 数据一致性保障

- **事务隔离**: 使用 SQLAlchemy 事务管理
- **多表联动**: 评论创建/删除时同时更新帖子计数和祖先回复计数
- **双写一致性**: 点赞记录和计数同时更新
- **防负数**: 取消点赞/删除评论时使用 `max(0, count - 1)`
- **唯一性**: 复合主键防止重复点赞
- **级联删除**: 用户/帖子/评论删除时自动清理关联数据

---

## 测试验证

### 测试覆盖场景

- ✅ 发布一级评论
- ✅ 发布回复（多级嵌套）
- ✅ reply_count 全量统计正确性
- ✅ comment_count 联动更新正确性
- ✅ 评论点赞/取消点赞
- ✅ 评论树查询（嵌套结构正确）
- ✅ 点赞状态注入正确
- ✅ 错误处理（帖子不存在、父评论不存在、权限验证）

### 测试脚本

测试文件: `test_comment.py`

运行命令:
```bash
python test_comment.py
```

测试结果: **全部通过**

测试输出示例:
```
📊 验证结果:
   - 评论 A (ID: 1) reply_count: 2 (期望: 2)
   - 评论 B (ID: 2) reply_count: 1 (期望: 1)
   - 评论 C (ID: 3) reply_count: 0 (期望: 0)
   - 帖子 comment_count: 3 (期望: 3)

📋 评论树结构:
   [ID:1] 这是一级评论 A
        点赞:1 🤍 回复:2
      └─ [ID:2] 这是回复 B，回复给 A
           点赞:1 👍 回复:1
         └─ [ID:3] 这是回复 C，回复给 B
              点赞:0 🤍 回复:0
```

---

## 注意事项

1. **并发安全**: 事务机制确保并发场景下的数据一致性
2. **性能优化**: 
   - 使用冗余计数避免频繁 COUNT 查询
   - 使用 `joinedload` 预加载减少 N+1 查询
   - 批量查询点赞状态避免循环查询
3. **级联删除**: 用户/帖子/评论删除时自动清理关联数据
4. **错误处理**: 完善的异常处理和 HTTP 状态码返回
5. **无限层级**: 通过自关联和递归算法支持无限层级回复

---

## 后续优化建议

1. 添加评论通知功能（回复通知、点赞通知）
2. 实现评论编辑功能
3. 添加评论举报功能
4. 实现热门评论排序算法
5. 考虑使用 Redis 缓存热点评论数据
6. 添加评论搜索功能
7. 实现评论置顶功能

---

**文档更新时间**: 2026.3.17 7:00  
**版本**: Alpha-v1.4.0-feat: 新增评论功能
