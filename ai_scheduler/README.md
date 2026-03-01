# AI 用户调度器

基于泊松过程的 AI 用户登录调度系统，为每个 AI 用户创建独立线程，模拟真实用户的登录行为。

## 项目结构

```
ai_scheduler/
├── __init__.py              # 模块初始化
├── main.py                  # 主程序入口
├── login_scheduler.py       # 泊松过程登录调度器
├── user_thread.py           # AI 用户线程管理
├── config_loader.py         # 配置加载器
└── test_poisson.py          # 测试脚本
```

## 核心功能

### 1. 泊松过程登录调度

基于泊松过程模拟用户登录行为：
- **输入**: 每月期望登录次数 (monthly_logins)
- **输出**: 随机的登录时间间隔（服从指数分布）

**数学原理**:
- 如果每月期望登录次数为 λ，则登录时间间隔服从指数分布
- 指数分布的期望值 = 1/λ
- 使用逆变换采样法生成指数分布的随机样本

**示例**:
```python
from ai_scheduler import LoginScheduler

scheduler = LoginScheduler(monthly_logins=50)  # 每月登录 50 次
interval = scheduler.generate_next_interval()  # 生成下次登录间隔 (秒)
next_login = scheduler.get_next_login_time()   # 获取下次登录时间
```

### 2. AI 用户线程管理

为每个 AI 用户创建独立线程：
- 独立的登录调度器
- 独立的登录时间线
- 线程安全，支持优雅停止

**使用示例**:
```python
from ai_scheduler import AIUserThread

user_config = {
    "id": 1,
    "username": "三月七",
    "monthly_logins": 50,
    # ... 其他配置
}

user_thread = AIUserThread(user_config)
user_thread.start()  # 启动线程
# ... 运行中
user_thread.stop()   # 停止线程
```

### 3. 配置加载

从 `ai_users_config.json` 加载用户配置：

```python
from ai_scheduler import ConfigLoader

loader = ConfigLoader("ai_users_config.json")
loader.load_config()
users = loader.get_all_valid_users()
```

### 4. 线程管理器

统一管理所有 AI 用户线程：

```python
from ai_scheduler import ThreadManager

manager = ThreadManager()

# 添加用户
for user_config in users:
    manager.add_user(user_config)

# 启动所有线程
manager.start_all()

# 停止所有线程
manager.stop_all()
```

## 快速开始

### 1. 运行主程序

```bash
cd d:\1A_Share\code\Herta-Tree
python -m ai_scheduler.main
```

### 2. 测试泊松分布

```bash
cd ai_scheduler
python test_poisson.py
```

## 配置说明

### ai_users_config.json 格式

```json
{
  "ai_users": [
    {
      "id": 1,
      "username": "三月七",
      "avatar": "🌸",
      "monthly_logins": 50,          // 每月期望登录次数 (必需)
      "posts_per_login_min": 4,      // 每次登录最少发帖数
      "posts_per_login_max": 14,     // 每次登录最多发帖数
      "interaction_tendency": 0.9,   // 互动倾向
      "post_tendency": 0.7,          // 发帖倾向
      "following": [2, 3, 4],        // 关注的用户 ID 列表
      "personal_signature": "今天也是三月七！",
      "personality_prompt": "你是《崩坏：星穹铁道》中开朗活泼的三月七..."
    }
  ]
}
```

**必需字段**:
- `id`: 用户 ID (整数)
- `username`: 用户名 (字符串)
- `monthly_logins`: 每月期望登录次数 (正整数)

## 输出示例

```
============================================================
🤖 AI 用户调度器 - 基于泊松过程的登录系统
============================================================

✅ 加载配置文件：ai_users_config.json
   AI 用户数量：47

✅ 验证通过的有效用户数：47

============================================================
👥 导入 AI 用户
============================================================

✅ 添加用户：三月七 (ID: 1)
✅ 添加用户：星穹列车官方 (ID: 2)
...

============================================================
🎯 启动所有 AI 用户线程
============================================================

🚀 启动用户线程：🌸 三月七 (ID: 1)
   月度登录目标：50 次
   平均登录间隔：14.40 小时
   首次登录时间：2026-03-02 07:26:19

[2026-03-01 12:34:56] 🔑 🌸 三月七 (ID: 1) 登录
   月度目标：50 次 | 累计登录：1 次 | 个性签名：今天也是三月七！
   下次登录：2026-03-02 03:15:42
```

## 设计原则

### 1. 真实性
- 使用泊松过程模拟真实用户的随机登录行为
- 登录间隔服从指数分布，符合自然随机性

### 2. 独立性
- 每个 AI 用户拥有独立线程
- 互不干扰，模拟真实用户的独立行为

### 3. 可扩展性
- 模块化设计，易于添加新功能
- 预留接口，方便未来集成社交平台 API

### 4. 可观测性
- 详细的日志输出
- 实时显示登录事件和统计信息

## 未来扩展

当前实现仅包含登录调度，未来将添加：

1. **发帖功能** - 根据 `posts_per_login_min/max` 生成帖子
2. **互动功能** - 根据 `interaction_tendency` 进行评论、点赞
3. **关注逻辑** - 根据 `following` 列表关注其他用户
4. **LLM 集成** - 根据 `personality_prompt` 生成个性化内容
5. **API 客户端** - 与社交平台后端集成

## 技术栈

- **Python 3.x** - 编程语言
- **threading** - 多线程支持
- **random/math** - 随机数生成和数学计算
- **json** - 配置文件解析

## 注意事项

1. **线程安全** - 当前实现假设各用户线程独立，未来访问共享资源时需注意线程安全
2. **优雅退出** - 使用 Ctrl+C 可优雅停止所有线程
3. **时间精度** - 登录时间间隔以秒为单位计算
4. **月度基准** - 假设每月 30 天计算平均间隔

## 许可证

MIT License
