# 信息流功能开发文档

## 版本信息

- **时间**: 2026.3.17 8:30
- **版本**: Alpha-v1.5.0-feat: 更新信息流
- **作者**: Herta-Tree 开发团队

---

## 功能概述

本次更新为 Herta-Tree 社交平台后端重构并增强了**信息流功能**，实现了前端友好的标准化响应结构，支持分页、预览评论、点赞状态等完整的信息流展示需求。

### 核心特性

- ✅ 标准化 API 响应结构（code, message, data, pagination）
- ✅ 分页功能（page, page_size, total, total_pages, has_next, has_prev）
- ✅ 帖子作者信息完整返回（author_id, author_name, author_avatar）
- ✅ 当前用户点赞状态（is_liked）
- ✅ 预览评论功能（每个帖子最多2条一级评论）
- ✅ 是否有更多评论标识（has_more_comments）
- ✅ 批量查询优化（避免 N+1 查询问题）
- ✅ 应用层分组实现预览评论限制

---

## 更改的文件

### 1. 新增文件

#### `app/schemas/response.py`
**更改说明**: 新建标准化响应模型
- `PaginationInfo`: 分页信息模型（page, page_size, total, total_pages, has_next, has_prev）
- `APIResponse[T]`: 泛型标准化响应模型（code, message, data, pagination）

#### `app/schemas/feed.py`
**更改说明**: 新建信息流相关 Pydantic Schemas
- `PostFeedItem`: 信息流帖子项
  - 基础字段：id, title, content, created_at
  - 作者信息：author_id, author_name, author_avatar
  - 统计字段：like_count, comment_count
  - 状态字段：is_liked, has_more_comments
  - 预览评论：preview_comments（List[CommentPreviewItem]）
- `CommentPreviewItem`: 评论预览项（id, content, created_at, owner_id, owner_name, owner_avatar, like_count）

#### `app/services/feed_service.py`
**更改说明**: 新建信息流业务逻辑层
- `_get_preview_comments()`: 批量获取预览评论（应用层分组，每个帖子最多2条）
- `_get_user_like_status()`: 批量获取用户点赞状态
- `_calculate_pagination()`: 计算分页信息
- `get_feed()`: 获取全局信息流（分页 + 完整数据组装）
- `get_user_feed()`: 获取指定用户的帖子流

### 2. 修改文件

#### `app/api/routers/feeds.py`
**更改说明**: 重构信息流路由控制器
- `GET /feed/all`: 全局信息流接口重构
  - 新增参数：page（默认1）, page_size（默认20）, current_user_id（可选）
  - 响应模型改为：`APIResponse[List[PostFeedItem]]`
  - 返回完整帖子信息：作者、点赞状态、预览评论、分页信息
- `GET /feed/user/{user_id}`: 用户帖子流接口重构
  - 新增参数：page（默认1）, page_size（默认20）, current_user_id（可选）
  - 响应模型改为：`APIResponse[List[PostFeedItem]]`
  - 返回完整帖子信息

---

## API 接口文档

### 信息流相关接口

| 接口 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/v1/feeds/feed/all` | GET | `page`, `page_size`, `current_user_id` | `APIResponse[List[PostFeedItem]]` |
| `/api/v1/feeds/feed/user/{user_id}` | GET | `page`, `page_size`, `current_user_id` | `APIResponse[List[PostFeedItem]]` |

### 接口详细说明

#### 1. 获取全局信息流

**请求示例：**
```bash
GET /api/v1/feeds/feed/all?page=1&page_size=20&current_user_id=123
```

**响应示例（200 OK）：**
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
      "is_liked": true,
      "has_more_comments": true,
      "preview_comments": [
        {
          "id": 1,
          "content": "确实不错！",
          "created_at": "2026-03-17T11:00:00",
          "owner_id": 2,
          "owner_name": "丹恒",
          "owner_avatar": "https://example.com/avatar2.jpg",
          "like_count": 3
        },
        {
          "id": 2,
          "content": "我也觉得！",
          "created_at": "2026-03-17T12:00:00",
          "owner_id": 3,
          "owner_name": "姬子",
          "owner_avatar": "https://example.com/avatar3.jpg",
          "like_count": 2
        }
      ]
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

#### 2. 获取用户帖子流

**请求示例：**
```bash
GET /api/v1/feeds/feed/user/1?page=1&page_size=20&current_user_id=123
```

**响应示例（200 OK）：** 同上

---

## 数据库设计

### 涉及表

#### `posts` 表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK, Auto | 帖子唯一ID |
| author_id | Integer | FK(users.id), Index, NonNull | 作者ID |
| title | String(200) | Nullable | 帖子标题 |
| content | Text | NonNull | 帖子内容 |
| like_count | Integer | Default 0, NonNull | 点赞数（冗余） |
| comment_count | Integer | Default 0, NonNull | 评论数（冗余） |
| created_at | DateTime | Default UTC | 创建时间 |

#### `users` 表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK, Auto | 用户唯一ID |
| username | String(50) | Unique, Index, NonNull | 用户名 |
| bio | Text | Nullable | 个人简介 |
| avatar_url | String(500) | Nullable | 头像URL |
| created_at | DateTime | Default UTC | 创建时间 |

#### `comments` 表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK, Auto | 评论唯一ID |
| post_id | Integer | FK(posts.id), Index, NonNull | 关联帖子ID |
| owner_id | Integer | FK(users.id), Index, NonNull | 评论发布者ID |
| parent_id | Integer | FK(comments.id), Index, Nullable | 父评论ID |
| content | Text | NonNull | 评论内容 |
| like_count | Integer | Default 0, NonNull | 点赞数（冗余） |
| created_at | DateTime | Default UTC | 创建时间 |

#### `likes` 表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| user_id | Integer | FK(users.id), PK | 点赞用户ID |
| post_id | Integer | FK(posts.id), PK | 被点赞帖子ID |
| created_at | DateTime | Default UTC | 点赞时间 |

---

## 业务逻辑说明

### 获取信息流流程

```
1. 查询帖子总数（用于分页计算）
   ↓
2. 查询帖子列表（分页 + joinedload 预加载作者）
   ↓
3. 批量查询当前用户点赞状态（IN 查询）
   ↓
4. 批量查询所有相关评论（IN 查询 + 预加载评论作者）
   ↓
5. 应用层按 post_id 分组，每个帖子取前 2 条一级评论
   ↓
6. 计算 has_more_comments = post.comment_count > len(preview_comments)
   ↓
7. 组装 PostFeedItem 列表
   ↓
8. 计算分页信息（total, total_pages, has_next, has_prev）
   ↓
9. 返回标准化响应结构
```

### 预览评论查询优化

**关键实现**：使用应用层分组而非 SQL LIMIT

```python
def _get_preview_comments(db, post_ids, limit_per_post=2):
    # 1. 批量查询所有一级评论
    all_comments = db.query(Comment).filter(
        Comment.post_id.in_(post_ids),
        Comment.parent_id == None
    ).options(
        joinedload(Comment.owner)
    ).order_by(
        Comment.post_id,
        Comment.created_at.desc()
    ).all()
    
    # 2. 应用层分组：按 post_id 分组，每个帖子取前 N 条
    result = defaultdict(list)
    for comment in all_comments:
        if len(result[comment.post_id]) < limit_per_post:
            result[comment.post_id].append(comment)
    
    return dict(result)
```

**原因**：SQL 的 LIMIT 无法作用于"每个分组"，必须使用应用层分组实现"每个帖子最多2条评论"。

### 性能优化策略

1. **joinedload 预加载**
   - `joinedload(Post.author)`: 避免 N+1 查询作者信息
   - `joinedload(Comment.owner)`: 避免 N+1 查询评论作者

2. **批量查询**
   - 使用 `IN` 查询一次性获取所有点赞状态
   - 使用 `IN` 查询一次性获取所有相关评论

3. **冗余计数**
   - `post.like_count`: 避免频繁 COUNT 查询
   - `post.comment_count`: 快速获取评论总数

---

## 测试验证

### 测试覆盖场景

- ✅ 分页功能（page, page_size, total_pages, has_next, has_prev）
- ✅ 预览评论限制（每个帖子最多2条）
- ✅ has_more_comments 计算正确性
- ✅ 点赞状态正确返回
- ✅ 作者信息完整返回
- ✅ 全局信息流接口
- ✅ 用户帖子流接口
- ✅ 错误处理（用户不存在返回 404）

### 测试脚本

测试文件: `test_feed.py`

运行命令:
```bash
python test_feed.py
```

测试结果: **全部通过**

测试输出示例:
```
============================================================
Feed 信息流接口测试
============================================================

初始化数据库...
✓ 数据库表创建完成

============================================================
创建测试数据...
============================================================
✓ 创建了 3 个测试用户
✓ 创建了 5 个测试帖子
✓ 创建了 11 条测试评论
✓ 创建了 3 条点赞记录

============================================================
测试全局信息流接口
============================================================

【测试1】获取第1页，每页3条
状态码: 200
消息: success
数据条数: 3
分页信息:
  - 当前页: 1
  - 每页条数: 3
  - 总条数: 5
  - 总页数: 2
  - 是否有下一页: True
  - 是否有上一页: False

【验证】预览评论数量（应≤2条）和 has_more_comments:
  帖子1: 2条预览评论, has_more_comments=True
  帖子2: 1条预览评论, has_more_comments=False
  帖子3: 2条预览评论, has_more_comments=False

【验证】点赞状态:
  帖子1: is_liked=False
  帖子2: is_liked=True
  帖子3: is_liked=True

============================================================
所有测试通过！
============================================================
```

---

## 注意事项

1. **分页参数**
   - `page` 从 1 开始（不是 0）
   - `page_size` 默认 20，最大 100
   - 超过总页数时返回空列表

2. **预览评论**
   - 只返回一级评论（parent_id IS NULL）
   - 按时间倒序排列（最新的在前）
   - 每个帖子最多 2 条

3. **has_more_comments**
   - 计算方式：`post.comment_count > len(preview_comments)`
   - 用于前端判断是否显示"查看全部评论"按钮

4. **current_user_id**
   - 可选参数，不提供时 `is_liked` 默认为 `false`
   - 用于判断当前用户是否点赞了帖子

5. **性能考虑**
   - 大数据量时预览评论查询可能较慢（需要加载所有评论再分组）
   - 可考虑使用窗口函数或缓存优化

---

## 后续优化建议

1. **性能优化**
   - 使用数据库窗口函数（ROW_NUMBER()）优化预览评论查询
   - 添加 Redis 缓存热点信息流数据
   - 实现信息流预加载机制

2. **功能扩展**
   - 添加信息流筛选功能（按时间范围、按标签等）
   - 实现个性化推荐算法
   - 添加信息流搜索功能

3. **监控与统计**
   - 添加接口性能监控
   - 统计热门帖子排行
   - 用户行为分析

---

**文档更新时间**: 2026.3.17 8:30  
**版本**: Alpha-v1.5.0-feat: 更新信息流
