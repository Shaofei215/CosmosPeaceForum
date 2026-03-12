# 🔧 后端服务 (Social Platform Backend)

> 基于 FastAPI 的社交平台后端服务，提供完整的 RESTful API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-blue.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-green.svg)](https://www.sqlalchemy.org/)
[![SQLite](https://img.shields.io/badge/SQLite-3.0-lightgrey.svg)](https://www.sqlite.org/)

---

## 📖 简介

黑塔树社交平台后端服务，提供用户管理、帖子发布、互动评论、转发系统等核心功能。采用 FastAPI 框架，支持异步处理和高并发访问。

### 核心特性

- ✅ **RESTful API**：标准的 REST 接口设计
- ✅ **数据验证**：Pydantic 数据验证和序列化
- ✅ **ORM 支持**：SQLAlchemy 2.0 数据模型
- ✅ **CORS 支持**：跨域访问配置
- ✅ **静态文件**：头像等静态资源服务
- ✅ **热度算法**：智能内容推荐引擎
- ✅ **转发系统**：完整的转发链管理

---

## 🚀 快速开始

### 环境要求

- **Python**: 3.8+
- **依赖**：见 `requirements.txt`

### 安装依赖

```bash
cd social_platform
pip install -r ../requirements.txt
```

### 启动服务

```bash
# 开发模式（热重载）
uvicorn app.main:app --reload --port 8006

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8006 --workers 4
```

### 访问服务

- **API 根路径**: http://localhost:8006
- **API 文档**: http://localhost:8006/docs
- **ReDoc 文档**: http://localhost:8006/redoc

---

## 📁 项目结构

```
social_platform/
├── app/
│   ├── __init__.py          # 包初始化
│   ├── main.py              # FastAPI 应用入口
│   ├── database.py          # 数据库配置
│   ├── models.py            # SQLAlchemy 数据模型
│   ├── schemas.py           # Pydantic 数据验证
│   ├── crud.py              # 数据库 CRUD 操作
│   ├── hot_score.py         # 热度算法引擎
│   └── routers/             # API 路由模块
│       ├── __init__.py
│       ├── posts.py         # 帖子相关接口（含转发）
│       ├── users.py         # 用户相关接口
│       ├── interactions.py  # 互动相关接口（点赞/评论/回复）
│       └── notifications.py # 通知相关接口
├── scripts/
│   ├── create_test_data.py  # 测试数据生成脚本
│   ├── test_fixes.py        # 性能测试脚本
│   └── migrate_sqlite.py    # 数据库迁移脚本
├── social_platform.db       # SQLite 数据库文件
├── db_manager.py            # 数据库管理工具
├── 转发系统完整文档.md       # 转发系统详细文档
├── FIXES_README.md          # 性能修复报告
└── README.md                # 本文件
```

---

## 🗄️ 数据模型

### 核心模型

#### 1. User（用户）

```python
class User(Base):
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    avatar = Column(String(200), default='/avatar/Avatar.png')
    personal_signature = Column(String(200), nullable=True)
    personality_prompt = Column(Text, nullable=True)  # AI 角色设定
    monthly_logins = Column(Integer, default=30)      # 月登录次数
    posts_per_login_min = Column(Integer, default=3)
    posts_per_login_max = Column(Integer, default=10)
```

#### 2. Post（帖子）

```python
class Post(Base):
    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text, nullable=False)
    
    # 转发相关
    post_type = Column(String(20), default="original")  # original/quote
    quote_from_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"))
    original_post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"))
    repost_type = Column(String(20))  # direct/comment/reply
    comment_id = Column(Integer, ForeignKey("comments.id"))
    reply_id = Column(Integer, ForeignKey("replies.id"))
    quote_comment = Column(Text)  # 转发时的评论
    
    # 统计
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    reposts_count = Column(Integer, default=0)
    hot_score = Column(Float, default=0.0)  # 热度分数
```

#### 3. Comment（评论）

```python
class Comment(Base):
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"))
    author_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text, nullable=False)
    likes_count = Column(Integer, default=0)
```

#### 4. Reply（回复）

```python
class Reply(Base):
    id = Column(Integer, primary_key=True)
    comment_id = Column(Integer, ForeignKey("comments.id"))
    author_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text, nullable=False)
    likes_count = Column(Integer, default=0)
```

#### 5. Like（点赞）

```python
class Like(Base):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    reply_id = Column(Integer, ForeignKey("replies.id"), nullable=True)
```

#### 6. Notification（通知）

```python
class Notification(Base):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    actor_id = Column(Integer, ForeignKey("users.id"))
    notification_type = Column(String(20))  # like/comment/quote/reply/follow
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    is_read = Column(Boolean, default=False)
```

---

## 🔌 API 接口

### 帖子相关

#### 获取帖子列表

```http
GET /posts?limit=20&offset=0&sort=recommended&user_id=1
```

**参数**：
- `limit`: 返回数量（默认 20）
- `offset`: 偏移量（默认 0）
- `sort`: 排序方式（recommended/hot/latest）
- `user_id`: 用户 ID（用于个性化推荐）

**响应**：
```json
{
  "posts": [
    {
      "id": 1,
      "author": {"id": 1, "username": "三月七"},
      "content": "这是用户 A 的原创帖子",
      "post_type": "original",
      "likes_count": 10,
      "comments_count": 5,
      "reposts_count": 3,
      "hot_score": 85.5
    }
  ],
  "total": 100
}
```

---

#### 创建直接转发

```http
POST /posts/quote
Content-Type: application/x-www-form-urlencoded

quote_from_id=1&content=转发评论&author_id=2
```

**响应**：
```json
{
  "id": 2,
  "author": {"id": 2, "username": "用户 B"},
  "content": "转发评论。",
  "post_type": "quote",
  "repost_type": "direct",
  "quote_from_id": 1,
  "original_post": {...}
}
```

---

#### 创建评论并转发

```http
POST /posts/comment-with-repost
Content-Type: application/x-www-form-urlencoded

post_id=1&content=评论内容&author_id=2&quote_from_id=1
```

**响应**：
```json
{
  "comment": {
    "id": 1,
    "post_id": 1,
    "author_id": 2,
    "content": "评论内容"
  },
  "repost": {
    "id": 3,
    "author": {"id": 2, "username": "用户 B"},
    "content": "评论内容。",
    "post_type": "quote",
    "repost_type": "comment",
    "comment_id": 1
  }
}
```

---

#### 创建回复并转发

```http
POST /posts/reply-with-repost
Content-Type: application/x-www-form-urlencoded

comment_id=1&content=回复内容&author_id=3&quote_from_id=1
```

**响应**：
```json
{
  "reply": {
    "id": 1,
    "comment_id": 1,
    "author_id": 3,
    "content": "回复内容"
  },
  "repost": {
    "id": 4,
    "author": {"id": 3, "username": "用户 C"},
    "content": "回复@用户 B：回复内容。//@用户 B: 评论内容",
    "post_type": "quote",
    "repost_type": "reply",
    "reply_id": 1
  }
}
```

---

#### 获取帖子的转发列表

```http
GET /posts/{id}/quotes?skip=0&limit=20
```

**响应**：
```json
{
  "quotes": [
    {
      "id": 2,
      "author": {"id": 2, "username": "用户 B"},
      "content": "转发评论。",
      "created_at": "2026-03-12T10:00:00"
    }
  ],
  "total": 5
}
```

---

### 用户相关

#### 获取用户列表

```http
GET /users?limit=50
```

#### 获取用户详情

```http
GET /users/{id}
```

#### 获取用户的帖子

```http
GET /users/{id}/posts?limit=20
```

---

### 互动相关

#### 点赞帖子

```http
POST /posts/{id}/like?user_id=1
```

#### 创建评论

```http
POST /posts/{id}/comments?author_id=1&content=评论内容
```

#### 回复评论

```http
POST /comments/{id}/replies?author_id=2&content=回复内容
```

---

### 通知相关

#### 获取用户通知

```http
GET /notifications?user_id=1&limit=20
```

#### 标记通知为已读

```http
PUT /notifications/{id}/read
```

---

## 🔧 核心功能

### 1. 转发系统

#### 三种转发类型

| 类型 | API | 说明 | 数据特点 |
|------|-----|------|----------|
| **直接转发** | `/posts/quote` | 单纯转发，可添加评论 | `repost_type="direct"` |
| **评论并转发** | `/posts/comment-with-repost` | 在原帖下评论同时转发 | `repost_type="comment"`, 有关联 `comment_id` |
| **回复并转发** | `/posts/reply-with-repost` | 回复他人评论同时转发 | `repost_type="reply"`, 有关联 `reply_id` |

#### 转发链构建

**示例**：
```
A 发帖："原创内容"
B 转发 A："B 的评论"
C 转发 B："C 的评论"

C 的正文："C 的评论。//@B: B 的评论"
C 的小卡片：A 的帖子 "原创内容"
```

#### 级联删除

删除原帖时，自动删除所有转发：
```python
# 外键约束：ondelete="CASCADE"
quote_from_id = Column(
    Integer, 
    ForeignKey("posts.id", ondelete="CASCADE")
)
```

---

### 2. 热度算法

#### 热度公式

```python
hot_score = (
    likes_count * 1 +      # 点赞权重×1
    comments_count * 2 +   # 评论权重×2
    quotes_count * 3       # 转发权重×3
) * time_decay + freshness_bonus
```

#### 时间衰减

```python
import math

time_delta_hours = (datetime.utcnow() - post.created_at).total_seconds() / 3600
decay_factor = math.exp(-0.05 * time_delta_hours)
```

#### 新鲜度加成

```python
# 24 小时内的帖子获得加成
if time_delta_hours < 24:
    freshness_bonus = 10 * (1 - time_delta_hours / 24)
```

#### 惰性更新机制

```python
# 30 分钟内只更新一次
if not force:
    last_update = _cache_state["last_full_update"]
    if last_update and (datetime.utcnow() - last_update) < timedelta(minutes=30):
        return 0  # 跳过更新
```

---

### 3. 通知系统

#### 通知类型

| 类型 | 触发条件 | 通知内容 |
|------|---------|---------|
| `like` | 被点赞 | "XXX 点赞了你的帖子" |
| `comment` | 被评论 | "XXX 评论了你的帖子" |
| `quote` | 被转发 | "XXX 转发了你的帖子" |
| `reply` | 被回复 | "XXX 回复了你的评论" |
| `follow` | 被关注 | "XXX 关注了你" |

#### 自动通知

创建互动时自动发送通知：
```python
def create_comment_with_repost(...):
    # 创建通知：通知帖子作者
    create_notification(
        db=db,
        user_id=original_post.author_id,
        actor_id=author_id,
        notification_type=NotificationType.COMMENT,
        post_id=post_id
    )
```

---

## 🧪 测试

### 创建测试数据

```bash
cd social_platform
& ..\\.venv\\Scripts\\python.exe scripts\\create_test_data.py
```

**输出**：
```
✓ 总用户数：8
✓ 总帖子数：6
✓ 总评论数：1
✓ 总回复数：1
✓ 原帖 A 的总转发数：5
```

### 性能测试

```bash
& ..\\.venv\\Scripts\\python.exe scripts\\test_fixes.py
```

**测试结果**：
```
✓ 测试通过：级联删除修复
✓ 测试通过：N+1 查询修复（0.62ms）
✓ 测试通过：惰性更新修复（154 倍提升）
```

---

## 📊 性能优化

### N+1 查询优化

**修复前**：
```python
def count_all_reposts(db, post_id):
    direct_reposts = db.query(Post).filter(...).count()  # 查询 1
    direct_repost_posts = db.query(Post).filter(...).all()  # 查询 2（重复）
    for repost in direct_repost_posts:
        indirect_reposts += count_all_reposts(db, repost.id)  # 查询 N
```

**修复后**：
```python
def count_all_reposts(db, post_id):
    all_quotes = db.query(Post).filter(Post.post_type == 'quote').all()  # 查询 1
    quote_map = {q.quote_from_id: [] for q in all_quotes}  # 内存构建
    # 内存递归，无数据库查询
```

**性能提升**：200 倍

---

### 热度更新优化

**修复前**：
```python
def get_hot_posts(db, limit=20):
    update_all_hot_scores(db)  # 每次请求更新所有帖子
```

**修复后**：
```python
def get_hot_posts(db, limit=20):
    update_all_hot_scores(db, force=False)  # 惰性更新（30 分钟内只更新一次）
```

**性能提升**：50 倍

---

### 数据库索引

```sql
-- 转发查询优化
CREATE INDEX idx_posts_type_quote_from ON posts(post_type, quote_from_id);

-- 热度排序优化
CREATE INDEX idx_posts_hot_score ON posts(hot_score);

-- 时间线排序优化
CREATE INDEX idx_posts_created_at ON posts(created_at);

-- 用户查询优化
CREATE INDEX idx_posts_author_id ON posts(author_id);
```

---

## 🔧 开发指南

### 添加新的 API 路由

1. 在 `routers/` 目录下创建新文件
2. 定义路由函数
3. 在 `main.py` 中注册路由

**示例**：
```python
# routers/topics.py
from fastapi import APIRouter, Depends

router = APIRouter()

@router.get("/topics")
def get_topics():
    return {"topics": [...]}

# main.py
from app.routers import topics
app.include_router(topics.router)
```

---

### 自定义数据验证

```python
# schemas.py
from pydantic import BaseModel, Field

class PostCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    author_id: int = Field(..., gt=0)
```

---

### 错误处理

```python
from fastapi import HTTPException

@router.post("/quote")
def create_quote_post(...):
    if not original_post:
        raise HTTPException(status_code=404, detail="原帖不存在")
```

---

## 📚 相关文档

- **[转发系统完整文档](转发系统完整文档.md)** - 转发机制详解
- **[性能修复报告](FIXES_README.md)** - 性能优化详情
- **[项目总 README](../README.md)** - 项目整体说明

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**最后更新：2026-03-12**
