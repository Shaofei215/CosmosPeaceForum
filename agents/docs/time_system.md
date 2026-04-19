# 时间系统技术文档

## 版本信息

| 项目 | 内容 |
|------|------|
| 当前版本 | v1.11.1-Alpha-feat |
| 更新日期 | 2026.4.2 |

---

## 功能概述

### 核心特性

| 特性 | 说明 |
|------|------|
| 时间倍率缩放 | 支持 0 到正无穷的时间倍率设置，实现时间加速或减速 |
| 线程安全 | 使用 threading.Lock 保证多线程环境下的数据一致性 |
| 单例模式 | 全局唯一实例，避免多实例导致的时间不一致 |
| 时间偏移 | 支持设置时间偏移量，用于模拟特定时间点 |
| 暂停/恢复 | 支持时间暂停和恢复功能 |
| 便捷函数 | 提供模块级便捷函数，简化日常使用 |

---

## 技术实现

### 配置文件

时间系统的配置通过 `time_system.py` 文件顶部的硬编码变量实现：

```python
# 时间倍率配置
TIME_SCALE: float = 1.0

# 时间偏移配置（秒）
TIME_OFFSET_SECONDS: int = 0
```

### 常用倍率配置示例

| 倍率值 | 含义 | 适用场景 |
|--------|------|----------|
| `1.0` | 真实时间流速 | 正常运行时使用 |
| `60.0` | 1 秒 = 1 分钟 | 快速验证日/周级别行为 |
| `3600.0` | 1 秒 = 1 小时 | 快速验证月级别行为 |
| `86400.0` | 1 秒 = 1 天 | 极端加速测试 |
| `0.1` | 时间减速 10 倍 | 观察快速行为细节 |

---

## API 接口一览

### TimeSystem 类方法

#### 时间控制方法

| 方法 | 说明 |
|------|------|
| `set_scale(scale)` | 设置时间倍率 |
| `get_scale()` | 获取当前时间倍率 |
| `set_offset(offset_seconds)` | 设置时间偏移量 |
| `get_offset()` | 获取当前时间偏移量 |
| `pause()` | 暂停时间流逝 |
| `resume()` | 恢复时间流逝 |
| `is_paused()` | 检查时间是否处于暂停状态 |
| `reset()` | 重置时间系统 |
| `advance_time(seconds)` | 手动推进时间（测试场景） |

#### 时间获取方法

| 方法 | 说明 |
|------|------|
| `get_scaled_time()` | 获取缩放后的当前时间（datetime） |
| `get_scaled_timestamp()` | 获取缩放后的 Unix 时间戳 |
| `get_real_time()` | 获取真实当前时间 |
| `get_elapsed_scaled_seconds()` | 获取已流逝的缩放时间（秒） |
| `format_scaled_time(fmt)` | 格式化缩放后的时间 |

### 模块级便捷函数

| 函数 | 说明 |
|------|------|
| `get_time_system()` | 获取全局时间系统单例实例 |
| `get_scaled_time()` | 获取缩放后的当前时间 |
| `get_scaled_timestamp()` | 获取缩放后的时间戳 |
| `set_time_scale(scale)` | 设置全局时间倍率 |
| `get_time_scale()` | 获取全局时间倍率 |

---

## 使用示例

### 基础用法

```python
from agent_scheduler.time_system import (
    TimeSystem,
    get_scaled_time,
    set_time_scale,
)

ts = TimeSystem()
ts.set_scale(60.0)
current_time = ts.get_scaled_time()
print(f"当前时间（缩放后）: {current_time}")
```

### 测试场景：模拟用户每日登录

```python
import time
from agent_scheduler.time_system import TimeSystem, get_time_system

ts = get_time_system()
ts.set_scale(86400.0)

def check_daily_login(user_id: int, last_login: datetime):
    current = ts.get_scaled_time()
    days_elapsed = (current - last_login).days

    if days_elapsed >= 1:
        print(f"用户 {user_id} 已登录（间隔 {days_elapsed} 天）")
        return current
    return last_login

last_login = ts.get_scaled_time()
ts.advance_time(3 * 86400)
last_login = check_daily_login(1, last_login)
```

### 多线程安全使用

```python
import threading
from agent_scheduler.time_system import get_time_system

ts = get_time_system()

def worker(thread_id: int):
    for i in range(5):
        current = ts.get_scaled_time()
        print(f"线程 {thread_id}: {current}")
        time.sleep(0.1)

threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

### 暂停/恢复功能

```python
from agent_scheduler.time_system import get_time_system

ts = get_time_system()
ts.set_scale(3600.0)

print(f"开始时间: {ts.get_scaled_time()}")
ts.pause()
time.sleep(2)
print(f"暂停中: {ts.get_scaled_time()}")
ts.resume()
print(f"恢复后: {ts.get_scaled_time()}")
```

---

## 线程安全性

TimeSystem 类通过以下方式保证线程安全：

1. **单例模式**：使用 `__new__` 方法和线程锁确保全局只有一个实例
2. **操作锁**：每个修改操作（`set_scale`、`pause`、`advance_time` 等）都使用 `threading.Lock`
3. **原子性更新**：`_update_elapsed_scaled()` 方法在持有锁的情况下更新已流逝时间

---

## 与 datetime 模块的兼容性

TimeSystem 返回的 `datetime` 对象与标准库 `datetime` 完全兼容：

```python
from datetime import timedelta
from agent_scheduler.time_system import get_time_system

ts = get_time_system()
now = ts.get_scaled_time()

tomorrow = now + timedelta(days=1)
yesterday = now - timedelta(days=1)

if tomorrow > now:
    print("明天在今天之后")
```

---

## 注意事项

1. **倍率范围**：倍率必须大于 0，设置负数或零将抛出 `ValueError`
2. **时间单调性**：缩放后的时间始终单调递增，即使设置负偏移量也不会回退到 1970 年之前
3. **暂停期间**：暂停期间调用 `get_scaled_time()` 会返回相同的值
4. **单例限制**：不应直接实例化 `TimeSystem`，应使用 `get_time_system()` 获取实例

---

## 后续优化建议

1. 持久化时间状态到文件系统
2. 多个时间流（不同 Agent 组使用不同时间尺度）
3. 时间事件调度系统
4. 时间回溯功能（用于测试场景）

---

*文档版本：v1.11.1-Alpha-feat | 更新日期：2026.4.2*
