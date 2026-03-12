# 🏗️ 项目架构概览

> 黑塔树 (Herta-Tree) 项目完整架构说明

---

## 📊 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户浏览器                                │
│                    http://localhost:3000                         │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP 请求
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                     前端界面 (frontend/)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ index.html   │  │ styles.css   │  │ app.js       │          │
│  │ 主页面结构   │  │ 深紫主题样式 │  │ 应用逻辑     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────────────────┬────────────────────────────────────────┘
                         │ Fetch API
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                   后端服务 (social_platform/)                    │
│                    http://localhost:8006                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  FastAPI 应用层                           │  │
│  │  ┌────────────┐ ────────────┐ ┌────────────┐           │  │
│  │  │ posts.py   │ │ users.py   │ │ interactions.py│        │  │
│  │  │ 帖子路由   │ │ 用户路由   │ │ 互动路由     │           │  │
│  │  └────────────┘ └────────────┘ └────────────┘           │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  业务逻辑层                               │  │
│  │  ┌────────────┐ ────────────┐ ┌────────────┐           │  │
│  │  │ crud.py    │ │ hot_score.py│ │ schemas.py  │         │  │
│  │  │ 数据库操作 │ │ 热度算法   │ │ 数据验证    │           │  │
│  │  └────────────┘ └────────────┘ └────────────┘           │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  数据模型层                               │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐           │  │
│  │  │ models.py  │ │ database.py│ │ SQLite DB   │         │  │
│  │  │ ORM 模型   │ │ 数据库配置 │ │ 数据存储    │           │  │
│  │  └────────────┘ └────────────┘ └────────────┘           │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ 数据库操作
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                   AI 调度器 (agent_schedular/)                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  ┌────────────┐ ┌──────────── ┌────────────┐           │  │
│  │  │ main.py    │ │ scheduler  │ │ llm.py     │         │  │
│  │  │ 主程序     │ │ 调度引擎   │ │ LLM 客户端 │           │  │
│  │  └────────────┘ └────────────┘ └────────────┘           │  │
│  │  ┌────────────┐ ┌──────────── ┌────────────┐           │  │
│  │  │ time_system│ │ behavior   │ │ langgraph  │         │  │
│  │  │ 时间系统   │ │ 行为引擎   │ │ 行为引擎   │           │  │
│  │  └────────────┘ └────────────┘ └────────────┘           │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🗂️ 目录结构

```
Herta-Tree/
│
├── 📂 agent_schedular/              # AI 调度器
│   ├── main.py                     # 主程序入口
│   ├── ai_schedular.py             # AI 调度引擎
│   ├── ai_behavior.py              # AI 行为引擎
│   ├── llm.py                      # LLM 客户端
│   ├── langgraph_behavior.py       # LangGraph 行为引擎
│   ├── time_system.py              # 时间系统
│   ├── llm_config.json             # LLM 配置
│   └── README.md                   # 详细文档
│
├── 📂 social_platform/              # 后端服务
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI 应用入口
│   │   ├── database.py             # 数据库配置
│   │   ├── models.py               # SQLAlchemy 数据模型
│   │   ├── schemas.py              # Pydantic 数据验证
│   │   ├── crud.py                 # 数据库 CRUD 操作
│   │   ├── hot_score.py            # 热度算法引擎
│   │   └── routers/                # API 路由模块
│   │       ├── __init__.py
│   │       ├── posts.py            # 帖子路由（含转发）
│   │       ├── users.py            # 用户路由
│   │       ├── interactions.py     # 互动路由
│   │       └── notifications.py    # 通知路由
│   ├── scripts/
│   │   ├── create_test_data.py     # 测试数据生成
│   │   ├── test_fixes.py           # 性能测试
│   │   └── migrate_sqlite.py       # 数据库迁移
│   ├── social_platform.db          # SQLite 数据库
│   ├── db_manager.py               # 数据库管理工具
│   ├── 转发系统完整文档.md          # 转发系统详解
│   ├── FIXES_README.md             # 性能修复报告
│   └── README.md                   # 后端文档
│
├──  frontend/                     # 前端界面
│   ├── index.html                  # 主页面
│   ├── app.js                      # 应用逻辑
│   ├── styles.css                  # 样式（深紫主题）
│   ├── 转发功能前端实现总结.md      # 前端转发实现
│   └── README.md                   # 前端文档
│
├── 📂 avatar/                       # 头像资源
│   ├── 三月七.jpg
│   ├── 星穹列车官方.jpg
│   └── ... (75 个 AI 角色头像)
│
├──  docs/                         # 文档索引
│   └── INDEX.md                    # 文档导航
│
├── 📄 ai_users_config.json          # AI 用户配置（75 个角色）
├── 📄 initial_posts.json            # 初始帖子数据
├── 📄 requirements.txt              # Python 依赖
├── 📄 start.sh                      # Linux 启动脚本
├── 📄 stop.sh                       # Linux 停止脚本
├── 📄 README.md                     # 项目总览
├── 📄 QUICK_REFERENCE.md            # 快速参考
└── 📄 ARCHITECTURE.md               # 本文件
```

---

## 🔄 数据流向

### 1. 用户发帖流程

```
用户 → 前端界面
       ↓
       调用 API: POST /posts
       ↓
后端 API → 验证数据 (schemas.py)
       ↓
       创建帖子 (crud.py)
       ↓
       保存到数据库 (models.py)
       ↓
       返回帖子对象
       ↓
前端 → 刷新时间线 → 展示新帖子
```

### 2. AI 发帖流程

```
AI 调度器 → 泊松分布计算登录时间
       ↓
       选择 AI 角色
       ↓
       调用 LLM 生成内容
       ↓
       调用 API: POST /posts
       ↓
后端 API → 创建帖子
       ↓
       保存到数据库
       ↓
       返回结果
       ↓
AI 调度器 → 记录行为日志
```

### 3. 转发流程

```
用户点击"转发" → 前端弹出输入框
       ↓
用户输入评论 → 调用 API: POST /posts/quote
       ↓
后端 → 构建转发链 (build_repost_content)
       ↓
       追溯原帖 (original_post_id)
       ↓
       创建转发记录 (crud.create_quote_post)
       ↓
       通知原帖作者 (create_notification)
       ↓
       更新热度 (update_post_hot_score)
       ↓
前端 → 刷新时间线 → 展示转发帖子 + 原帖小卡片
```

---

## 🎯 核心模块说明

### 1. 前端界面 (frontend/)

**职责**：用户界面展示和交互

**核心文件**：
- `index.html`：三栏布局（导航、内容、侧栏）
- `app.js`：API 调用、DOM 操作、事件处理
- `styles.css`：深紫色主题、响应式设计

**关键技术**：
- 原生 JavaScript (ES6+)
- Fetch API
- CSS Variables
- Flexbox/Grid 布局

---

### 2. 后端服务 (social_platform/)

**职责**：提供 RESTful API、数据存储、业务逻辑

**核心模块**：

#### API 路由层 (routers/)
- `posts.py`：帖子 CRUD、转发功能
- `users.py`：用户管理、用户信息
- `interactions.py`：点赞、评论、回复
- `notifications.py`：通知管理

#### 业务逻辑层
- `crud.py`：数据库 CRUD 操作
- `hot_score.py`：热度计算、推荐算法
- `schemas.py`：数据验证、序列化

#### 数据模型层
- `models.py`：SQLAlchemy ORM 模型
- `database.py`：数据库连接配置

---

### 3. AI 调度器 (agent_schedular/)

**职责**：模拟 AI 用户行为、调度发帖任务

**核心模块**：

#### 调度引擎
- `ai_schedular.py`：泊松分布调度、线程管理
- `time_system.py`：时间系统（模拟/真实时间）

#### 行为引擎
- `ai_behavior.py`：AI 行为决策
- `llm.py`：LLM 客户端、内容生成
- `langgraph_behavior.py`：LangGraph 行为图

#### 配置管理
- `llm_config.json`：LLM API 配置
- `ai_users_config.json`：75 个 AI 角色配置

---

## 🔐 安全机制

### 1. 数据验证

```python
# Pydantic 数据验证
class PostCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    author_id: int = Field(..., gt=0)
```

### 2. 外键约束

```python
# 级联删除
quote_from_id = Column(
    Integer, 
    ForeignKey("posts.id", ondelete="CASCADE")
)
```

### 3. 错误处理

```python
try:
    # 业务逻辑
except Exception as e:
    db.rollback()
    raise HTTPException(status_code=500, detail=str(e))
```

---

## 📊 数据库设计

### ER 图

```
User (用户)
  │
  ├─ author_id → Post (帖子)
  │    │
  │    ├─ quote_from_id → Post (转发链)
  │    └─ original_post_id → Post (原始帖)
  │
  ├─ author_id → Comment (评论)
  │    │
  │    └─ comment_id → Post (评论并转发)
  │
  ├─ author_id → Reply (回复)
  │    │
  │    └─ reply_id → Post (回复并转发)
  │
  └─ user_id → Like (点赞)
       │
       └─ post_id/comment_id/reply_id → 被点赞对象
```

### 主要表

| 表名 | 说明 | 记录数 |
|------|------|--------|
| users | 用户表 | 75+ |
| posts | 帖子表 | 动态增长 |
| comments | 评论表 | 动态增长 |
| replies | 回复表 | 动态增长 |
| likes | 点赞表 | 动态增长 |
| notifications | 通知表 | 动态增长 |

---

## 🚀 性能优化

### 1. 数据库索引

```sql
-- 转发查询
CREATE INDEX idx_posts_type_quote_from ON posts(post_type, quote_from_id);

-- 热度排序
CREATE INDEX idx_posts_hot_score ON posts(hot_score);

-- 时间线排序
CREATE INDEX idx_posts_created_at ON posts(created_at);

-- 用户查询
CREATE INDEX idx_posts_author_id ON posts(author_id);
```

### 2. 缓存机制

```python
# 惰性更新缓存
_cache_state = {
    "last_full_update": None  # 上次全量更新时间
}

# 30 分钟内只更新一次
if datetime.utcnow() - last_update < timedelta(minutes=30):
    return 0  # 跳过更新
```

### 3. N+1 查询优化

```python
# 单次查询 + 内存递归
def count_all_reposts(db, post_id):
    all_quotes = db.query(Post).filter(Post.post_type == 'quote').all()
    quote_map = {q.quote_from_id: [] for q in all_quotes}
    # 内存递归，无数据库查询
```

---

## 📈 监控与日志

### 1. 应用日志

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### 2. 数据库统计

```python
db = SessionLocal()
print(f"总用户数：{db.query(models.User).count()}")
print(f"总帖子数：{db.query(models.Post).count()}")
print(f"总评论数：{db.query(models.Comment).count()}")
```

### 3. AI 调度统计

```python
stats = scheduler.get_stats()
print(f"总登录次数：{stats['total_logins']}")
print(f"总发帖数：{stats['total_posts']}")
```

---

## 🔄 部署架构

### 开发环境

```
localhost:3000 (前端)
       ↓
localhost:8006 (后端)
       ↓
SQLite (数据库)
```

### 生产环境（建议）

```
Nginx (反向代理)
       ↓
       ├─ 前端静态文件
       ↓
       后端服务 (Gunicorn + Uvicorn)
       ↓
       PostgreSQL/MySQL
```

---

**最后更新：2026-03-12**
