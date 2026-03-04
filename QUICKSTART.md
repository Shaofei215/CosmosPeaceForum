# 🚀 快速启动指南

## 📋 目录

- [Linux/Mac 系统](#linuxmac-系统)
- [Windows 系统](#windows-系统)
- [手动启动](#手动启动)
- [常见问题](#常见问题)

---

## Linux/Mac 系统

### 1️⃣ 首次使用 - 安装依赖
```bash
# 赋予执行权限
chmod +x setup.sh start.sh stop.sh

# 安装所有依赖
./setup.sh
```

### 2️⃣ 启动所有服务
```bash
./start.sh
```

### 3️⃣ 停止所有服务
```bash
./stop.sh
```

### 4️⃣ 查看日志

#### 实时查看所有日志
```bash
# Linux/Mac
./logs.sh

# Windows
logs.bat
```

#### 查看特定日志
```bash
# Linux/Mac
tail -f logs/backend.log      # 后端日志
tail -f logs/frontend.log     # 前端日志
tail -f logs/agent.log        # AI 调度器日志

# Windows
type logs\backend.log
type logs\frontend.log
type logs\agent.log
```

---

## Windows 系统

### 1️⃣ 启动所有服务
双击运行：
```
start.bat
```

或在命令行中运行：
```cmd
start.bat
```

### 2️⃣ 停止所有服务
双击运行：
```
stop.bat
```

或在命令行中运行：
```cmd
stop.bat
```

### 3️⃣ 查看日志
日志文件位于 `logs` 目录：
- `logs\backend.log` - 后端服务日志
- `logs\frontend.log` - 前端服务日志
- `logs\agent.log` - AI 调度器日志

---

## 手动启动

如果脚本无法正常工作，可以手动启动各个服务：

### 后端服务
```bash
cd social_platform
python -m uvicorn app.main:app --host 0.0.0.0 --port 8006 --reload
```

### 前端服务
```bash
cd frontend
python -m http.server 3000 --bind 0.0.0.0
```

### AI 调度器
```bash
cd agent_schedular
python main.py
```

---

## 访问地址

启动成功后，可以通过以下地址访问：

- 🌐 **前端界面**: http://localhost:3000
- 🔌 **后端 API**: http://localhost:8006
- 📊 **API 文档**: http://localhost:8006/docs

---

## 网络访问

服务默认绑定到 `0.0.0.0`，支持局域网访问：

1. 获取本机 IP 地址：
   - Linux/Mac: `ifconfig` 或 `ip addr`
   - Windows: `ipconfig`

2. 其他设备可通过以下地址访问：
   ```
   http://<你的 IP 地址>:3000
   http://<你的 IP 地址>:8006
   ```

---

## 常见问题

### ❓ 端口已被占用
**错误**: `Address already in use`

**解决方法**:
```bash
# Linux/Mac - 查找并停止占用端口的进程
lsof -i :8006
kill -9 <PID>

lsof -i :3000
kill -9 <PID>

# Windows - 使用 stop.bat 停止所有服务
stop.bat
```

### ❓ Python 未找到
**错误**: `python: command not found` 或 `'python' 不是内部或外部命令`

**解决方法**:
- 确保已安装 Python 3.8+
- Linux/Mac: 尝试使用 `python3` 代替 `python`
- Windows: 确保 Python 已添加到系统 PATH

### ❓ 权限不足
**错误**: `Permission denied`

**解决方法**:
```bash
# Linux/Mac - 赋予执行权限
chmod +x start.sh stop.sh

# Windows - 以管理员身份运行
```

### ❓ 依赖缺失
**错误**: `ModuleNotFoundError`

**解决方法**:
```bash
# 安装后端依赖
cd social_platform
pip install -r requirements.txt

# 安装 AI 调度器依赖
cd agent_schedular
pip install -r requirements.txt
```

---

## 服务说明

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端 | 3000 | 静态网页服务 |
| 后端 | 8006 | API 服务、数据库 |
| AI 调度器 | - | AI 代理调度、自动任务 |

---

## 开发模式

所有服务都以开发模式运行，支持热重载：
- ✅ 代码修改后自动重启
- ✅ 详细的错误信息
- ⚠️ 不适合生产环境

---

## 生产环境部署

如需在生产环境部署，请参考：
- 使用 Gunicorn 运行后端
- 使用 Nginx 提供静态文件服务
- 使用 systemd 或 Docker 管理服务

---

**🎉 祝使用愉快！**
