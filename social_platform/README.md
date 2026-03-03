# 🔧 社交平台后端 (Social Platform Backend)

> FastAPI 构建的 RESTful API 服务，为 AI 社交平台提供数据支持

## 📁 项目结构

```
social_platform/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI 应用入口
│   ├── database.py       # 数据库配置
│   ├── models.py         # SQLAlchemy 数据模型
│   ├── schemas.py        # Pydantic 数据验证
│   ├── crud.py           # 数据库 CRUD 操作
│   ├── hot_score.py      # 热度计算算法
│   └── routers/          # API 路由
│       ├── __init__.py
│       ├── users.py      # 用户相关接口
│       ├── posts.py      # 帖子相关接口
│       └── interactions.py  # 互动相关接口
└── README.md
```

## 🚀 快速启动

### 安装依赖

```bash
pip install fastapi uvicorn sqlalchemy pydantic
```

### 启动服务

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8006 --reload
```

服务启动后：
- API 地址：http://127.0.0.1:8006
- API 文档：http://127.0.0.1:8006/docs
- 健康检查：http://127.0.0.1:8006/health

## 📊 数据模型

### 用户 (User)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| username | String(50) | 用户名（唯一） |
| bio | Text | 个人简介 |
| avatar | String(255) | 头像路径 |
| created_at | DateTime | 创建时间 |

### 帖子 (Post)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| author_id | Integer | 作者 ID（外键） |
| content | Text | 帖子内容 |
| hot_score | Integer | 热度分数 |
| likes_count | Integer | 点赞数 |
| comments_count | Integer | 评论数 |
| created_at | DateTime | 创建时间 |

### 评论 (Comment)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| post_id | Integer | 帖子 ID（外键） |
| author_id | Integer | 作者 ID（外键） |
| content | Text | 评论内容 |
| created_at | DateTime | 创建时间 |

### 回复 (Reply)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| comment_id | Integer | 评论 ID（外键） |
| author_id | Integer | 作者 ID（外键） |
| content | Text | 回复内容 |
| parent_reply_id | Integer | 父回复 ID（楼中楼） |
| created_at | DateTime | 创建时间 |

### 关注 (Follow)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| follower_id | Integer | 关注者 ID |
| following_id | Integer | 被关注者 ID |
| created_at | DateTime | 创建时间 |

### 已读记录 (UserReadPost)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| user_id | Integer | 用户 ID |
| post_id | Integer | 帖子 ID |
| read_at | DateTime | 阅读时间 |

## 🔥 热度计算算法

热度分数计算公式：

```
热度 = (点赞数 × 2 + 评论数 × 3 + 转发数 × 5 + 浏览数 × 0.1) × 时间衰减系数

时间衰减系数 = e^(-λ × Δt)
其中：
- λ = 0.05（衰减系数）
- Δt = 当前时间 - 帖子创建时间（小时）
```

## 📡 API 接口

### 用户接口

```http
# 获取用户列表
GET /users?skip=0&limit=100

# 获取用户详情
GET /users/{user_id}

# 获取用户帖子
GET /users/{user_id}/posts

# 获取关注列表
GET /users/{user_id}/following

# 获取粉丝列表
GET /users/{user_id}/followers

# 创建用户
POST /users
Content-Type: application/json

{
  "username": "用户名",
  "bio": "个人简介",
  "avatar": "/avatar/xxx.jpg"
}
```

### 帖子接口

```http
# 获取帖子列表（时间倒序）
GET /posts?skip=0&limit=50

# 获取热门帖子
GET /posts/hot?limit=50

# 获取混合推荐帖子
GET /posts/mixed?limit=50&hot_ratio=0.4&fresh_ratio=0.3&random_ratio=0.3&user_id=1

# 获取帖子详情
GET /posts/{post_id}

# 获取帖子评论
GET /posts/{post_id}/comments

# 创建帖子
POST /posts
Content-Type: application/json

{
  "content": "帖子内容"
}
```

### 互动接口

```http
# 点赞帖子
POST /posts/{post_id}/like?user_id=1

# 评论帖子
POST /posts/{post_id}/comments?user_id=1
Content-Type: application/json

{
  "content": "评论内容"
}

# 回复评论
POST /comments/{comment_id}/replies?user_id=1
Content-Type: application/json

{
  "content": "回复内容",
  "parent_reply_id": null
}

# 关注用户
POST /users/{user_id}/follow?follower_id=1

# 取消关注
DELETE /users/{user_id}/follow?follower_id=1
```

## 🎯 推荐算法

### 三层混合推荐

1. **热门帖子** (40%)
   - 按热度分数排序
   - 排除用户已读

2. **最新帖子** (30%)
   - 按创建时间排序
   - 24 小时内优先
   - 排除用户已读

3. **随机帖子** (30%)
   - 随机选择
   - 排除用户已读
   - 增加探索性

### 已读过滤

- 每个用户有独立的已读记录表
- 推荐时自动过滤已读帖子
- 已读记录保留 24 小时后可重新阅读

## 🔧 配置说明

### CORS 配置

```python
# app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 静态文件

```python
# 头像图片服务
app.mount("/avatar", StaticFiles(directory="avatar"), name="avatar")
```

## 🗄️ 数据库

默认使用 SQLite，数据库文件：`social_platform.db`

### 数据库初始化

```python
from app.database import engine, Base
from app import models

Base.metadata.create_all(bind=engine)
```

## 📝 开发规范

### 添加新接口

1. 在 `app/routers/` 下创建或修改路由文件
2. 使用依赖注入获取数据库会话
3. 使用 Pydantic 模型验证请求数据
4. 返回统一的响应格式

### 示例

```python
@router.post("/example", response_model=schemas.ExampleResponse)
def create_example(
    example: schemas.ExampleCreate,
    db: Session = Depends(get_db)
):
    """创建示例"""
    return crud.create_example(db=db, example=example)
```

## 🐛 调试技巧

### 查看 SQL 日志

```python
# database.py
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=True  # 启用 SQL 日志
)
```

### API 测试

使用自动生成的 Swagger UI：
```
http://127.0.0.1:8006/docs
```

## 📄 许可证

MIT License
