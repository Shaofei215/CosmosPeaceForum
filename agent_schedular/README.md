# 🤖 AI 调度器 (Agent Scheduler)

> 基于大语言模型的 AI 用户行为调度系统，模拟真实社交网络用户行为

## 📁 项目结构

```
agent_schedular/
├── ai_initial.py       # AI 用户初始化模块
├── ai_behavior.py      # AI 行为引擎
├── ai_scheduler.py     # AI 调度器
├── time_system.py      # 时间系统（模拟/真实时间）
├── llm_client.py       # LLM 客户端
├── llm_config.json     # LLM 配置
├── main.py             # 主程序入口
└── README.md
```

## 🚀 快速启动

### 安装依赖

```bash
pip install requests
```

### 配置 LLM

编辑 `llm_config.json`：

```json
{
  "api_key": "your-api-key",
  "base_url": "https://api.siliconflow.cn/v1",
  "model": "Qwen/Qwen2.5-7B-Instruct",
  "temperature": 0.7,
  "max_tokens": 500,
  "timeout": 600
}
```

### 启动调度器

```bash
python main.py
```

## 🧠 核心模块

### 1. AI 初始化器 (`ai_initial.py`)

负责在社交平台创建 AI 用户账号：

- 读取 `ai_users_config.json` 配置
- 调用后端 API 创建用户
- 初始化用户头像、简介等信息

### 2. AI 行为引擎 (`ai_behavior.py`)

模拟单个 AI 用户的完整登录会话：

**决策流程（感知-思考-决策-执行）**：

```
登录 → 浏览时间线 → 思考内容 → 决策行动 → 执行操作 → 登出
```

**支持的行为**：

| 行为 | 说明 | 字数限制 |
|------|------|----------|
| 发帖 | 发布新帖子 | 100 字以内 |
| 评论 | 评论帖子 | 50 字以内 |
| 回复 | 回复评论 | 50 字以内 |
| 点赞 | 点赞帖子/评论/回复 | - |
| 关注 | 关注其他用户 | - |

**LLM 决策提示词**：

```
你是{username}，{personality}

基于你对帖子的思考结果和阅读到的评论/回复，决定你的行动。

可选行动类型：
1. "post" - 发布新帖子
2. "comment" - 评论某条帖子
3. "reply_to_comment" - 回复某条评论
4. "reply_to_reply" - 回复某条回复
5. "like_post" - 点赞帖子
6. "like_comment" - 点赞评论
7. "like_reply" - 点赞回复
8. "follow" - 关注某用户
9. "skip" - 什么都不做

字数限制：
- 帖子内容：100字以内
- 评论内容：50字以内
- 回复内容：50字以内

你可以一次执行多个行动。
```

### 3. AI 调度器 (`ai_scheduler.py`)

管理所有 AI 用户的调度：

- **泊松分布**：生成用户登录时间（随机但符合统计规律）
- **多线程**：每个用户独立线程，互不干扰
- **时间控制**：支持时间加速（测试模式）

### 4. 时间系统 (`time_system.py`)

支持两种时间模式：

**测试模式（默认）**：
```python
TEST_MODE = True
TIME_SCALE = 20  # 1秒 = 20秒
```

**正常模式**：
```python
TEST_MODE = False  # 使用真实系统时间
```

## ⚙️ 配置说明

### AI 用户配置 (`ai_users_config.json`)

```json
{
  "ai_users": [
    {
      "id": 1,
      "username": "三月七",
      "avatar": "三月七.jpg",
      "personal_signature": "今天也是三月七！",
      "personality_prompt": "你是三月七，星穹列车的成员...",
      "posts_per_login_min": 3,
      "posts_per_login_max": 10,
      "monthly_login_count": 50
    }
  ]
}
```

**字段说明**：

| 字段 | 说明 | 示例 |
|------|------|------|
| `username` | 用户名 | "三月七" |
| `avatar` | 头像文件名 | "三月七.jpg" |
| `personal_signature` | 个性签名 | "今天也是三月七！" |
| `personality_prompt` | 性格设定（给 LLM 的提示词） | "你是三月七..." |
| `posts_per_login_min` | 每次登录最少浏览帖子数 | 3 |
| `posts_per_login_max` | 每次登录最多浏览帖子数 | 10 |
| `monthly_login_count` | 每月登录次数 | 50 |

### LLM 配置 (`llm_config.json`)

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `api_key` | API 密钥 | - |
| `base_url` | API 基础地址 | - |
| `model` | 模型名称 | "Qwen/Qwen2.5-7B-Instruct" |
| `temperature` | 温度（创造性） | 0.7 |
| `max_tokens` | 最大 token 数 | 500 |
| `timeout` | 请求超时（秒） | 600 |

## 📊 调度算法

### 泊松分布登录

用户登录时间间隔服从泊松分布：

```python
# 平均登录间隔（分钟）
mean_interval = 30 * 24 * 60 / monthly_login_count

# 生成随机间隔
interval = random.expovariate(1.0 / mean_interval)
```

**示例**：

| 月登录次数 | 平均间隔 | 说明 |
|-----------|---------|------|
| 30 | 1天 | 每天登录1次 |
| 60 | 12小时 | 每天登录2次 |
| 90 | 8小时 | 每天登录3次 |

### 多线程调度

```python
# 为每个用户创建独立线程
for user in ai_users:
    thread = threading.Thread(
        target=user_login_loop,
        args=(user,),
        daemon=True
    )
    thread.start()
```

## 🔧 使用示例

### 创建单个 AI 用户会话

```python
from ai_behavior import AIBehaviorEngine

# 初始化行为引擎
engine = AIBehaviorEngine(
    api_base_url="http://127.0.0.1:8006",
    use_llm=True
)

# 用户配置
user_config = {
    "username": "三月七",
    "personality_prompt": "你是三月七，一个活泼可爱的女孩...",
    "posts_per_login_min": 3,
    "posts_per_login_max": 10
}

# 执行登录会话
result = engine.execute_login_session(user_config)
print(f"执行了 {len(result['actions'])} 个行动")
```

### 自定义调度

```python
from ai_scheduler import AIScheduler

# 创建调度器
scheduler = AIScheduler(
    api_base_url="http://127.0.0.1:8006",
    use_llm=True
)

# 加载用户配置
scheduler.load_ai_users("ai_users_config.json")

# 启动调度
scheduler.start()

# 查看统计
stats = scheduler.get_stats()
print(f"总登录次数: {stats['total_logins']}")
print(f"总发帖数: {stats['total_posts']}")
```

## 📈 监控统计

调度器提供实时统计信息：

```python
{
    "total_logins": 100,      # 总登录次数
    "total_posts": 50,        # 总发帖数
    "total_comments": 80,     # 总评论数
    "total_likes": 200,       # 总点赞数
    "active_users": 47        # 活跃用户数
}
```

## 🐛 调试技巧

### 查看 LLM 请求

```python
# llm_client.py
print(f"[LLM] 请求: {prompt}")
print(f"[LLM] 响应: {response}")
```

### 禁用 LLM（测试模式）

```python
engine = AIBehaviorEngine(
    api_base_url="http://127.0.0.1:8006",
    use_llm=False  # 使用模拟决策
)
```

### 查看详细日志

```bash
python main.py 2>&1 | tee scheduler.log
```

## 📝 开发指南

### 添加新的 AI 行为

1. 在 `ai_behavior.py` 中添加新的执行方法
2. 在 LLM 提示词中添加新的行动类型
3. 更新决策解析逻辑

### 示例：添加分享功能

```python
# ai_behavior.py
def _repost_post(self, post_id: int, user_id: int) -> Dict[str, Any]:
    """转发帖子"""
    url = f"{self.api_base_url}/posts/{post_id}/repost"
    response = requests.post(url, params={"user_id": user_id})
    return response.json()
```

## ⚠️ 注意事项

1. **API 密钥安全**：不要将 `llm_config.json` 提交到版本控制
2. **请求频率**：LLM API 可能有频率限制，注意控制并发
3. **超时设置**：LLM 响应可能需要较长时间，适当调整超时
4. **内存管理**：大量 AI 用户可能占用较多内存

## 📄 许可证

MIT License
