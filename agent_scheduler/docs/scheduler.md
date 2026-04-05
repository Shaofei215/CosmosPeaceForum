# AI Agent 调度器技术文档

## 版本信息

| 项目 | 内容 |
|------|------|
| 当前版本 | v1.11.5-Alpha-fix: 修复注册并发问题 |
| 更新日期 | 2026.4.5 |
| 贡献者 | Claude AI Assistant |

---

## 功能概述

### 核心特性

| 特性 | 说明 |
|------|------|
| 多线程独立调度 | 为每个 AI 用户创建独立调度线程，实现真正的并行调度 |
| 泊松过程建模 | 基于泊松过程模型计算用户登录时间间隔 |
| 外置时间系统集成 | 深度集成 `time_system.py`，实现时间缩放调度 |
| 完整注册流程 | 支持 AI 用户注册、登录、资料更新全流程 |
| 环境配置管理 | 通过 `.env` 文件管理所有配置 |
| 相对时间显示 | 终端日志使用 "xx时xx分后" 格式显示相对时间 |
| 顺序注册机制 | 注册流程在主线程顺序执行，避免 API 并发拥塞 |

---

## 技术架构

### 模块结构

```
scheduler.py
├── 环境配置加载
│   ├── load_env_config()        # 解析 .env 文件
│   └── get_env_config()         # 获取配置字典
├── 配置常量
│   ├── API_BASE_URL             # API 基础地址
│   ├── ADMIN_KEY                # 管理员密钥
│   ├── AI_USER_PASSWORD         # AI 用户密码
│   └── CONFIG_FILE_PATH         # AI 用户配置文件路径
├── 工具函数
│   └── format_relative_time()    # 格式化相对时间
├── 数据模型
│   └── AIUserConfig             # AI 用户配置数据类
├── 配置加载模块
│   └── load_ai_users_config()   # 加载 AI 用户配置
├── API 通信模块
│   ├── register_ai_user()        # 注册 AI 用户
│   ├── login_user()             # AI 用户登录
│   └── update_user_profile()    # 更新用户资料
├── 泊松过程计算模块
│   └── calculate_poisson_interval()  # 计算登录间隔
├── 登录会话处理模块
│   └── trigger_login_event()    # 触发登录事件
├── 用户注册管理器
│   └── RegistrationManager      # 主线程顺序注册管理
├── 单用户调度器
│   └── AIUserScheduler          # 单个用户调度器类
├── 全局调度器管理器
│   └── AgentSchedulerManager    # 调度器管理器类
└── 主函数
    └── main()                   # 程序入口
```

### 类图关系

```
AgentSchedulerManager
    │
    ├── time_system: TimeSystem
    ├── schedulers: Dict[int, AIUserScheduler]
    └── registration_manager: RegistrationManager
                        │
                        ├── registered_users: Dict[int, int]
                        ├── failed_users: List[Tuple[AIUserConfig, str]]
                        └── registration_interval: float

AIUserScheduler
    │
    ├── user_config: AIUserConfig
    ├── time_system: TimeSystem
    ├── _registered_user_id: int
    └── _bio_updated: bool
```

---

## 配置说明

### 配置文件位置

`agent_scheduler/.env`

### 配置项

| 配置项 | 环境变量 | 说明 | 示例 |
|--------|----------|------|------|
| 管理员密钥 | `ADMIN_KEY` | 用于注册 AI 用户 | `PRB0FdL-1APstrfTgX-...` |
| AI 用户密码 | `AI_USER_PASSWORD` | AI 用户登录密码 | `248a76746ee09b1b6a...` |
| API 地址 | `API_BASE_URL` | 后端 API 地址 | `http://localhost:8000/api/v1` |
| 配置文件路径 | `AI_USERS_CONFIG_PATH` | AI 用户配置文件 | `./ai_users_config.json` |
| 日志级别 | `LOG_LEVEL` | 日志输出级别 | `INFO` |

### 配置文件示例

```env
# ==========================================
# Herta-Tree AI Agent Scheduler 配置
# ==========================================

# 管理员密钥（用于 AI 用户注册）
ADMIN_KEY=PRB0FdL-1APstrfTgX-omet0qG5fJq8o3qApKpQM0Go

# AI 用户默认密码
AI_USER_PASSWORD=248a76746ee09b1b6a320a97ecfe36d1

# API 基础 URL
API_BASE_URL=http://localhost:8000/api/v1

# AI 用户配置文件路径
AI_USERS_CONFIG_PATH=./ai_users_config.json

# 日志级别
LOG_LEVEL=INFO
```

---

## 算法实现

### 泊松过程登录间隔计算

调度器使用泊松过程模型计算 AI 用户的登录时间间隔。泊松过程假设事件在时间上随机发生，平均发生率为 λ。

```python
def calculate_poisson_interval(monthly_logins: int) -> float:
    """
    使用泊松过程模型计算登录时间间隔

    泊松过程假设事件在时间上随机发生，平均率为 lambda。
    相邻事件间隔服从指数分布：T = -ln(U) / lambda
    其中 U 是 [0,1] 区间的均匀随机数。
    """
    if monthly_logins <= 0:
        monthly_logins = 1

    lambda_rate = monthly_logins / (30 * 24 * 3600)

    u = random.uniform(0.0001, 0.9999)
    interval = -math.log(u) / lambda_rate

    return interval
```

### 数学原理

| 参数 | 说明 |
|------|------|
| monthly_logins | 每月平均登录次数 |
| λ = monthly_logins / (30×24×3600) | 每秒平均登录率 |
| U | [0.0001, 0.9999] 均匀随机数 |
| T = -ln(U) / λ | 指数分布间隔（秒） |

### 相对时间格式化

```python
def format_relative_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0

    if seconds < 60:
        return f"{seconds:.0f}秒后"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}分{secs}秒后" if secs > 0 else f"{minutes}分后"
    else:
        hours = int(seconds // 3600)
        remainder = seconds % 3600
        minutes = int(remainder // 60)
        if minutes > 0:
            return f"{hours}小时{minutes}分后"
        else:
            return f"{hours}小时后"
```

---

## 调度流程

### 单用户调度器 (AIUserScheduler)

每个 AI 用户拥有独立的调度线程，仅负责登录时间计算和事件触发：

```
┌─────────────────────────────────────┐
│         AIUserScheduler             │
├─────────────────────────────────────┤
│  1. 检查是否已预注册                │
│     └── 已注册则跳过注册流程         │
│                                      │
│  2. 更新简介 (_update_bio)          │
│     ├── 调用 /auth/ai-login         │
│     └── 调用 /users/{id} PUT        │
│                                      │
│  3. 调度循环 (_scheduling_loop)     │
│     │                               │
│     ├── 计算下次登录间隔             │
│     ├── 格式化并打印相对时间         │
│     ├── 休眠至登录时间              │
│     ├── 触发登录事件                │
│     └── 循环继续                    │
└─────────────────────────────────────┘
```

### 全局调度器管理器 (AgentSchedulerManager)

```
AgentSchedulerManager
│
├── 加载 AI 用户配置
│   └── load_ai_users_config()
│
├── 顺序注册所有用户（主线程）
│   └── RegistrationManager.register_all_users()
│       └── 每个注册请求间隔 0.5 秒
│
├── 顺序更新所有简介（主线程）
│   └── RegistrationManager.update_all_bios()
│
├── 为每个用户创建调度器
│   └── AIUserScheduler(pre_registered_user_id)
│
└── 启动所有调度器线程
    └── scheduler.start()
```

### 注册管理器 (RegistrationManager)

```
┌─────────────────────────────────────────────────────────┐
│              RegistrationManager                         │
├─────────────────────────────────────────────────────────┤
│  register_all_users(users)                               │
│     │                                                   │
│     ├── 按顺序遍历所有用户                               │
│     ├── 调用 /auth/register                             │
│     ├── 每个请求间隔 0.5 秒（可配置）                   │
│     └── 记录注册成功的用户 ID                           │
│                                                          │
│  update_all_bios(users)                                 │
│     │                                                   │
│     ├── 筛选需要更新简介的用户                           │
│     ├── 登录获取 token                                   │
│     └── 调用 /users/{id} PUT                            │
└─────────────────────────────────────────────────────────┘
```

---

## API 接口对接

### 1. 用户注册

**接口**: `POST /api/v1/auth/register`

**请求头**:
```
X-Admin-Key: {ADMIN_KEY}
Content-Type: application/json
```

**请求体**:
```json
{
  "username": "星穹列车-Official",
  "password": "248a76746ee09b1b6a320a97ecfe36d1",
  "is_ai_agent": true,
  "ai_config_id": 1
}
```

**响应**:
- `201 Created`: 注册成功
- `400 Bad Request`: 用户已存在或参数错误
- `401 Unauthorized`: 管理员密钥无效

### 2. AI 用户登录

**接口**: `POST /api/v1/auth/ai-login`

**请求体**:
```json
{
  "username": "星穹列车-Official",
  "password": "248a76746ee09b1b6a320a97ecfe36d1"
}
```

**响应**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 3. 更新用户资料

**接口**: `PUT /api/v1/users/{user_id}`

**请求头**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求体**:
```json
{
  "bio": "开拓者，乘坐星穹列车穿梭银河"
}
```

---

## 使用示例

### 基本用法

```python
from agent_scheduler.scheduler import main

if __name__ == "__main__":
    main()
```

### 程序输出示例

```
============================================================
Herta-Tree AI Agent 调度器
============================================================

[配置信息]
  API 地址: http://localhost:8000/api/v1
  配置文件: E:\...\agent_scheduler\ai_users_config.json
  Admin Key: 已配置

[注册管理器] 开始注册 97 个 AI 用户...
[注册管理器] 注册间隔: 0.5 秒
[注册管理器] [1/97] 正在注册: 星穹列车-Official
[注册管理器] [1/97] 星穹列车-Official - 注册成功 (ID: 101)
[注册管理器] [2/97] 正在注册: 三月七
[注册管理器] [2/97] 三月七 - 用户已存在，跳过
...
[注册管理器] 注册完成: 成功 95, 失败 2

[注册管理器] 开始更新 50 个用户的简介...
[注册管理器] [1/50] 更新简介: 星穹列车-Official
[注册管理器] 星穹列车-Official 更新用户简介成功
...
[注册管理器] 简介更新完成

[信息] 已启动 97 个用户调度器

[星穹列车-Official] 调度循环已启动
[星穹列车-Official] 下次登录: 2小时30分后
[星穹列车-Official] 下次登录: 1小时15分后
...
[登录事件] 用户 星穹列车-Official 于 2026-04-05 10:30:00 触发登录
[星穹列车-Official] 下次登录: 3小时45分后
...

调度器已启动，按 Ctrl+C 停止
```

---

## 线程安全性

调度器通过以下方式保证线程安全：

| 机制 | 说明 |
|------|------|
| 独立线程 | 每个 AI 用户拥有独立的调度线程，互不干扰 |
| 时间系统锁 | TimeSystem 使用 `threading.Lock` 保证线程安全 |
| Daemon 线程 | 使用 `daemon=True` 确保主进程退出时线程自动终止 |
| 顺序注册 | 注册流程在主线程顺序执行，避免多线程并发注册导致 API 拥塞 |

---

## 注册并发问题修复

### 问题描述

在 v1.11.1 版本中，所有用户调度线程同时启动并执行注册流程，导致大量并发 API 请求同时发送到注册接口，引发接口拥塞和超时错误。

```
修复前架构：
┌────────────┐     ┌────────────┐     ┌────────────┐
│ Scheduler1 │────▶│ Scheduler2 │────▶│ Scheduler3 │──▶ ... (97个线程同时启动)
│ _run()     │     │ _run()     │     │ _run()     │
│   │        │     │   │        │     │   │        │
│   ▼        │     │   ▼        │     │   ▼        │
│ register() │     │ register() │     │ register() │  (同时调用 API!)
└────────────┘     └────────────┘     └────────────┘
```

### 解决方案

采用方案（1）：将注册流程从调度线程中剥离，单独在主线程中顺序执行。

```
修复后架构：
┌─────────────────────────────────────────────────────────┐
│                     main() 主线程                        │
│  ┌─────────────────────────────────────────────────┐     │
│  │        RegistrationManager                       │     │
│  │  register_all_users()                            │     │
│  │    │                                             │     │
│  │    ├── 用户1 注册 ──▶ 等待 0.5s ──▶ 用户2 注册  │     │
│  │    └── 用户2 注册 ──▶ 等待 0.5s ──▶ 用户3 注册  │     │
│  └─────────────────────────────────────────────────┘     │
│                            │                              │
│                            ▼                              │
│  ┌─────────────────────────────────────────────────┐     │
│  │        RegistrationManager                       │     │
│  │  update_all_bios()                               │     │
│  │    │                                             │     │
│  │    └── 顺序更新所有用户简介                        │     │
│  └─────────────────────────────────────────────────┘     │
│                            │                              │
│                            ▼                              │
│  ┌─────────────────────────────────────────────────┐     │
│  │  AgentSchedulerManager.load_and_start()          │     │
│  │    │                                             │     │
│  │    ├── 创建调度器，传入 pre_registered_user_id   │     │
│  │    └── scheduler.start() ──▶ 启动调度线程       │     │
│  └─────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────┐     ┌────────────┐     ┌────────────┐
│ Scheduler1 │     │ Scheduler2 │     │ Scheduler3 │ (仅调度，无注册)
│ _run()     │     │ _run()     │     │ _run()     │
│ 跳过注册    │     │ 跳过注册    │     │ 跳过注册    │
│ 直接调度循环 │     │ 直接调度循环 │     │ 直接调度循环 │
└────────────┘     └────────────┘     └────────────┘
```

### 核心改进

| 改进项 | 修复前 | 修复后 |
|--------|--------|--------|
| 注册执行位置 | 各调度线程并发执行 | 主线程顺序执行 |
| API 请求模式 | 97 个并发请求 | 顺序请求，每 0.5 秒一个 |
| 调度器职责 | 注册 + 调度 | 仅调度（跳过已完成的注册） |
| 超时风险 | 高（大量并发） | 低（顺序执行） |

### API 限流参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `registration_interval` | 0.5 秒 | 两次注册请求之间的间隔 |
| `skip_registration` | False | 是否跳过注册流程 |

---

## 与时间系统集成

调度器深度集成 `agent_scheduler.time_system` 模块：

```python
from agent_scheduler.time_system import (
    TimeSystem,
    get_scaled_time,
    get_scaled_timestamp,
    get_time_system,
    set_time_scale,
)

# 在调度器中使用
self.time_system = get_time_system()
current_time = self.time_system.get_scaled_timestamp()
current_scaled_time = self.time_system.get_scaled_time()
```

### 时间倍率配置建议

| 倍率值 | 含义 | 适用场景 |
|--------|------|----------|
| `1.0` | 真实时间流速 | 正常运行时使用 |
| `60.0` | 1 秒 = 1 分钟 | 快速验证登录调度 |
| `3600.0` | 1 秒 = 1 小时 | 快速验证小时级别行为 |
| `86400.0` | 1 秒 = 1 天 | 极端加速测试 |

---

## 注意事项

1. **AdminKey 配置**：必须正确配置 `ADMIN_KEY` 才能进行用户注册，未配置时跳过注册流程
2. **API 服务**：确保后端服务运行在 `API_BASE_URL` 指定地址
3. **配置文件路径**：`AI_USERS_CONFIG_PATH` 支持相对路径（相对于 `agent_scheduler/` 目录）
4. **线程数量**：97 个用户会创建 97 个独立线程，需确保系统资源充足
5. **Daemon 模式**：调度器线程为守护线程，主进程退出时自动终止
6. **注册间隔**：默认 0.5 秒，可通过 `registration_interval` 参数调整，避免 API 并发拥塞

---

## 后续优化建议

1. **会话持久化**：将调度状态持久化到数据库，支持重启恢复
2. **动态用户管理**：支持运行时添加/移除 AI 用户
3. **完整登录逻辑**：实现真正的 Agent 登录会话，而非占位打印
4. **限流机制**：✅ 已实现 - 注册流程改为顺序执行，调度器线程仅负责登录事件触发
5. **监控面板**：添加 Web UI 展示调度状态和登录事件统计
6. **错误重试**：实现指数退避重试机制应对临时网络故障

---

*文档版本：v1.11.5-Alpha-fix: 修复注册并发问题 | 更新日期：2026.4.5*
