# AI 调度器使用指南

## 快速开始

### 1. 启动社交平台后端

```bash
cd social_platform
uvicorn app.main:app --reload
```

后端将在 `http://127.0.0.1:8000` 启动。

### 2. 启动 AI 调度器

在新终端窗口：

```bash
cd agent_schedular
python main.py
```

## 配置说明

### 时间系统配置

在 [`time_system.py`](time_system.py) 中配置：

```python
# 测试模式开关
TEST_MODE = True  # True: 测试模式，False: 正常模式

# 测试模式配置
SIMULATION_START_HOUR = 0  # 模拟时间起始点
SIMULATION_START_MINUTE = 0  # 模拟时间起始点
TIME_SCALE = 60  # 时间流速倍率 (1 秒 = 60 秒)
```

**模式说明：**
- **测试模式**：使用加速的模拟时间，从 00:00 开始，便于快速调试
- **正常模式**：使用系统真实时间

### AI 用户配置

配置文件位于项目根目录的 [`ai_users_config.json`](../ai_users_config.json)

每个 AI 用户包含：
- `username`: 用户名
- `personal_signature`: 个性签名
- `monthly_logins`: 每月理想登录次数
- `personality_prompt`: 个性提示（待使用）
- 其他配置...

## 工作原理

### 1. 用户初始化
- 从 `ai_users_config.json` 加载配置
- 在社交平台中创建用户（使用用户名和个性签名）
- 用户已存在时自动复用，不会重复创建

### 2. 登录调度
- 每个 AI 用户独立线程运行
- 使用**泊松过程**计算下次登录时间间隔
- 公式：`delay = -ln(U) / λ`
  - `U`: (0,1) 均匀随机数
  - `λ`: 每小时平均登录次数 = `monthly_logins / (30 * 24)`

### 3. 登录操作（MVP）
**重要说明**："登录"仅作为一次瞬时操作，不存在"在线"状态。

当前版本仅打印登录信息：
```
[2026-03-02 00:00:50] [三月七] 登录成功
[三月七] 下次登录将在 29.59 小时后
```

## 项目结构

```
agent_schedular/
├── __init__.py           # 模块初始化
├── time_system.py        # 独立时间系统
├── ai_initial.py         # AI 用户配置加载及初始化
├── ai_schedular.py       # AI 用户线程调度器
└── main.py              # 主入口
```

## 核心功能

### time_system.py
- **单例模式**：全局唯一时间实例
- **双模式支持**：测试模式/正常模式
- **时间加速**：测试模式下可调节时间流速
- **API**：
  - `time_system.now()`: 获取当前时间
  - `time_system.sleep(seconds)`: 休眠（自动适配时间流速）
  - `time_system.get_mode()`: 获取当前模式

### ai_initial.py
- **配置加载**：从 JSON 文件加载用户配置
- **用户创建**：调用社交平台 API 创建用户
- **重复检测**：自动处理用户已存在情况
- **API**：
  - `load_config()`: 加载配置
  - `initialize_all_users()`: 初始化所有用户
  - `get_user_by_id(user_id)`: 获取用户信息

### ai_schedular.py
- **线程管理**：每个用户独立线程
- **泊松调度**：基于配置的理想登录次数
- **瞬时登录**：登录仅为时刻操作，无状态追踪
- **简洁输出**：仅显示必要信息（运行状态、用户线程数、时间模式）
- **API**：
  - `start()`: 启动调度器
  - `stop()`: 停止调度器
  - `print_status()`: 打印状态

## 测试验证

运行测试：

```bash
# 测试时间系统
cd agent_schedular
python time_system.py

# 测试完整流程
python main.py
```

预期输出：
1. 时间系统启动信息
2. 47 个 AI 用户初始化成功
3. 用户线程逐个启动
4. 用户开始登录（测试模式下快速发生）
5. 每 30 秒打印一次调度器状态

## 停止调度器

按 `Ctrl+C` 优雅停止调度器。

## 注意事项

1. **先启动后端**：确保社交平台后端已启动
2. **配置文件路径**：自动使用项目根目录的 `ai_users_config.json`
3. **用户持久化**：创建的用户保存在 SQLite 数据库中
4. **重复运行**：可安全重复运行，不会创建重复用户

## 后续开发

当前为 MVP 版本，后续可扩展：
- [ ] 登录后的行为逻辑（发帖、评论、点赞）
- [ ] 基于 LLM 的内容生成
- [ ] 社交互动策略
- [ ] 更复杂的调度算法
- [ ] 用户行为日志记录
