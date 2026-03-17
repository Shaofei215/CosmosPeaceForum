# 信息流功能开发文档

## 版本信息

- **时间**: 2026.3.17 22:00
- **版本**: Alpha-v1.5.1-chore: 移除评论预览
- **作者**: Herta-Tree 开发团队

---

## 功能概述

本次更新为 Herta-Tree 社交平台后端重构并增强了**信息流功能**，实现了前端友好的标准化响应结构，支持分页、点赞状态等完整的信息流展示需求。

### 核心特性

- ✅ 标准化 API 响应结构（code, message, data, pagination）
- ✅ 分页功能（page, page_size, total, total_pages, has_next, has_prev）
- ✅ 帖子作者信息完整返回（author_id, author_name, author_avatar）
- ✅ 当前用户点赞状态（is_liked）
- ✅ 批量查询优化（避免 N+1 查询问题）

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
  - 状态字段：is_liked

#### `app/services/feed_service.py`
**更改说明**: 新建信息流业务逻辑层
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
  - 返回完整帖子信息：作者、点赞状态、分页信息
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
      "is_liked": true
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
4. 组装 PostFeedItem 列表
   ↓
5. 计算分页信息（total, total_pages, has_next, has_prev）
   ↓
6. 返回标准化响应结构
```

### 性能优化策略

1. **joinedload 预加载**
   - `joinedload(Post.author)`: 避免 N+1 查询作者信息

2. **批量查询**
   - 使用 `IN` 查询一次性获取所有点赞状态

3. **冗余计数**
   - `post.like_count`: 避免频繁 COUNT 查询
   - `post.comment_count`: 快速获取评论总数

---

## 测试验证

### 测试覆盖场景

- ✅ 分页功能（page, page_size, total_pages, has_next, has_prev）
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

---

## 注意事项

1. **分页参数**
   - `page` 从 1 开始（不是 0）
   - `page_size` 默认 20，最大 100
   - 超过总页数时返回空列表

2. **current_user_id**
   - 可选参数，不提供时 `is_liked` 默认为 `false`
   - 用于判断当前用户是否点赞了帖子

3. **评论获取**
   - 信息流接口不返回评论内容
   - 评论详情通过独立接口 `/api/v1/posts/{post_id}/comments` 获取

---

## 后续优化建议

1. **性能优化**
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

## 更新历史

### Alpha-v1.5.0-feat (2026.3.17 8:30)
- 初始版本，包含预览评论功能
- 标准化 API 响应结构
- 分页功能
- 作者信息和点赞状态

### Alpha-v1.5.1-chore (2026.3.17 22:00)
- 移除预览评论功能
- 简化 Feed 接口响应结构
- 评论详情通过独立接口获取

---

**文档更新时间**: 2026.3.17 22:00  
**版本**: Alpha-v1.5.1-chore: 移除评论预览
