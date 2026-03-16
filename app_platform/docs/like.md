# 点赞功能开发文档

## 版本信息

- **时间**: 2026.3.17 6:05
- **版本**: Alpha-1.3.0-feat: 新增点赞功能
- **作者**: Herta-Tree 开发团队

---

## 功能概述

本次更新为 Herta-Tree 社交平台后端新增了完整的**点赞功能**，采用"冗余计数 + 关联记录"的混合模式设计，确保高并发场景下的数据一致性和查询性能。

### 核心特性

- ✅ 点赞/取消点赞切换机制
- ✅ 事务保证双写一致性
- ✅ 冗余计数优化查询性能
- ✅ 复合主键防止重复点赞
- ✅ 完整的错误处理机制

---

## 更改的文件

### 1. 新增文件

#### `app/models/like.py`
**更改说明**: 新建点赞数据库模型
- 定义 `Like` 模型类，记录用户与帖子的点赞关系
- 使用 `(user_id, post_id)` 复合主键确保唯一性
- 添加外键约束（`ondelete="CASCADE"`）保证参照完整性
- 创建索引优化查询性能（`idx_likes_post_id`, `idx_likes_user_id`）
- 建立与 `User` 和 `Post` 的双向关联关系

#### `app/schemas/like.py`
**更改说明**: 新建点赞相关 Pydantic Schemas
- `LikeToggleResponse`: 点赞操作响应模型（post_id, like_count, is_liked）
- `LikeStatusMixin`: 点赞状态混入类（is_liked_by_current_user）
- `LikeCountResponse`: 点赞数响应模型

#### `app/services/like_service.py`
**更改说明**: 新建点赞业务逻辑层
- `PostNotFoundError`: 帖子不存在异常
- `DuplicateLikeError`: 重复点赞异常
- `toggle_like()`: 点赞/取消切换（事务保证双写一致性）
- `get_like_status()`: 获取点赞状态
- `get_post_like_count()`: 获取帖子点赞数
- `is_user_liked()`: 检查用户是否已点赞

#### `app/api/routers/like.py`
**更改说明**: 新建点赞路由控制器
- `POST /posts/{post_id}/like`: 点赞/取消点赞切换
- `GET /posts/{post_id}/like-status`: 查询点赞状态

### 2. 修改文件

#### `app/models/post.py`
**更改说明**: 扩展帖子模型
- 新增 `like_count` 字段（Integer，默认 0，非空）
- 新增 `likes` 关联关系（与 `Like` 模型双向关联）

#### `app/models/user.py`
**更改说明**: 扩展用户模型
- 新增 `likes` 关联关系（与 `Like` 模型双向关联）

#### `app/schemas/post.py`
**更改说明**: 扩展帖子 schemas
- `PostResponse` 新增 `like_count` 字段（默认 0）
- 新增 `PostCreate` 的 `author_id` 字段（必填）
- 新增 `PostResponseWithLikeStatus` 类（继承 PostResponse + is_liked_by_current_user）

#### `app/api/routers/posts.py`
**更改说明**: 扩展帖子路由
- 修改 `GET /posts/{post_id}` 接口
  - 响应模型改为 `PostResponseWithLikeStatus`
  - 新增可选查询参数 `user_id`
  - 根据 user_id 动态计算 `is_liked_by_current_user`
- 导入 `Like` 模型和 `PostResponseWithLikeStatus` schema

#### `app/main.py`
**更改说明**: 注册点赞路由
- 导入 `like` 路由模块
- 注册路由：`app.include_router(like.router, prefix=f"{settings.API_V1_PREFIX}/posts", tags=["likes"])`

---

## API 接口文档

### 点赞相关接口

| 接口 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/v1/posts/{post_id}/like` | POST | `user_id` (query, 必填) | `LikeToggleResponse` |
| `/api/v1/posts/{post_id}/like-status` | GET | `user_id` (query, 必填) | `{is_liked, like_count}` |

### 扩展接口

| 接口 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/v1/posts/{post_id}` | GET | `user_id` (query, 可选) | `PostResponseWithLikeStatus` |

### 响应示例

#### 点赞/取消点赞
```json
{
  "post_id": 1,
  "like_count": 2,
  "is_liked": true
}
```

#### 帖子详情（带点赞状态）
```json
{
  "id": 1,
  "author_id": 3,
  "title": "测试帖子",
  "content": "这是一个用于测试点赞功能的帖子内容",
  "created_at": "2026-03-16T22:02:50.196678",
  "like_count": 2,
  "is_liked_by_current_user": true
}
```

---

## 数据库设计

### 新增表

#### `likes` 表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| user_id | Integer | ForeignKey(users.id), PK | 点赞用户 ID |
| post_id | Integer | ForeignKey(posts.id), PK | 被点赞帖子 ID |
| created_at | DateTime | 默认当前时间 | 点赞创建时间 |

**索引**:
- 复合主键: `(user_id, post_id)`
- `idx_likes_post_id`: 加速帖子点赞查询
- `idx_likes_user_id`: 加速用户点赞查询

### 扩展表

#### `posts` 表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| like_count | Integer | 默认 0, 非空 | 点赞计数（冗余存储） |

---

## 业务逻辑说明

### 点赞/取消点赞流程

1. **检查帖子是否存在**
   - 不存在则抛出 `PostNotFoundError`

2. **检查当前点赞状态**
   - 查询 `likes` 表是否存在记录

3. **执行切换操作**（在事务中）
   - **点赞**: `INSERT INTO likes` + `UPDATE posts SET like_count = like_count + 1`
   - **取消点赞**: `DELETE FROM likes` + `UPDATE posts SET like_count = like_count - 1`

4. **提交事务**
   - 任何一步失败则回滚整个事务

### 数据一致性保障

- **事务隔离**: 使用 SQLAlchemy 事务管理
- **双写一致性**: 点赞记录和计数同时更新
- **防负数**: 取消点赞时使用 `max(0, like_count - 1)`
- **唯一性**: 复合主键防止重复点赞

---

## 测试验证

### 测试覆盖场景

- ✅ 用户点赞帖子
- ✅ 用户取消点赞
- ✅ 多用户点赞同一帖子
- ✅ 点赞状态查询
- ✅ 帖子详情带点赞状态
- ✅ 错误处理（帖子不存在返回 404）

### 测试脚本

测试文件: `test_like.py`

运行命令:
```bash
python test_like.py
```

测试结果: **全部通过**

---

## 注意事项

1. **并发安全**: 事务机制确保并发场景下的数据一致性
2. **性能优化**: 使用冗余计数避免频繁 COUNT 查询
3. **级联删除**: 用户或帖子删除时自动清理点赞记录
4. **错误处理**: 完善的异常处理和 HTTP 状态码返回

---

## 后续优化建议

1. 添加点赞通知功能
2. 实现批量点赞状态查询
3. 添加点赞排行榜接口
4. 考虑使用 Redis 缓存热点帖子点赞数

---

**文档更新时间**: 2026.3.17 6:05  
**版本**: Alpha-1.3.0-feat: 新增点赞功能
