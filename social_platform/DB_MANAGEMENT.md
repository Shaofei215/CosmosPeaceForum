# 数据库管理工具

快速管理和维护社交平台数据库的命令行工具。

## 📋 功能列表

| 命令 | 功能 | 说明 |
|------|------|------|
| `show-tables` | 显示所有表 | 查看数据库中所有表及记录数 |
| `show-users` | 显示用户列表 | 查看所有用户的 ID、用户名、个人简介 |
| `delete-user ID` | 删除用户 | 根据 ID 删除用户及其所有相关数据 |
| `delete-name 名称` | 删除用户 | 根据用户名删除用户 |
| `delete-all` | 清空数据 | 删除所有用户数据（保留表结构） |
| `reset` | 重置数据库 | 完全删除数据库文件 |
| `clean-ai` | 清理 AI 用户 | 仅清理配置文件中定义的 AI 用户 |

## 💡 使用示例

### 1. 查看数据库状态

```bash
# 查看所有表及记录数
python db_manager.py show-tables

# 查看所有用户
python db_manager.py show-users
```

**输出示例：**
```
📊 数据库表列表:
============================================================
users                - 48 条记录
posts                - 125 条记录
comments             - 89 条记录
likes                - 234 条记录
follows              - 156 条记录
============================================================
```

### 2. 删除单个用户

```bash
# 根据 ID 删除
python db_manager.py delete-user 5

# 根据用户名删除
python db_manager.py delete-name 三月七
```

**说明：** 会自动级联删除该用户的帖子、评论、点赞、关注关系

### 3. 清理 AI 用户（推荐）

```bash
python db_manager.py clean-ai
```

**功能：** 
- 读取 `ai_users_config.json` 配置文件
- 仅删除配置中定义的 AI 用户
- 保留其他手动创建的用户
- **适用于开发过程中重置 AI 用户**

### 4. 清空所有数据

```bash
python db_manager.py delete-all
```

**警告：** 会删除所有用户数据，但保留数据库表结构

### 5. 完全重置数据库

```bash
python db_manager.py reset
```

**功能：**
- 自动备份当前数据库（`.db.backup`）
- 删除数据库文件
- 重启后端后会自动创建新数据库

## ⚠️ 注意事项

### 1. 关于重复创建用户

**问题：** 反复启动 AI 调度器是否会造成数据库中的用户反复创建？

**答案：** ❌ **不会**

**原因：**
- 社交平台后端在 `users.py` 第 20 行检查用户名是否已存在
- 如果用户名已存在，返回 400 错误，不会创建重复用户
- AI 调度器的 `user_initializer.py` 会捕获 400 错误，并自动查找已存在的用户
- 使用已存在用户的 ID，不会造成数据混乱

**测试验证：**
```
第一次启动：
创建用户：三月七 (ID: 1)
✅ 创建成功 - 平台 ID: 2

第二次启动：
创建用户：三月七 (ID: 1)
⚠️  用户已存在 - 平台 ID: 2  # 检测到已存在，不会重复创建
```

### 2. 关于数据持久化

**问题：** 用户初始化后是否会被保存在数据库？

**答案：** ✅ **是的，永久保存**

**说明：**
- 用户数据保存在 `social_platform.db` SQLite 数据库文件中
- 即使重启后端服务，数据也会保留
- 删除数据库文件或执行清空操作才会丢失数据

### 3. 开发环境建议

**推荐工作流程：**

1. **日常开发测试：**
   ```bash
   # 清理 AI 用户
   python db_manager.py clean-ai
   
   # 重启 AI 调度器
   python -m ai_scheduler.main
   ```

2. **完全重置（遇到奇怪问题时）：**
   ```bash
   # 重置数据库
   python db_manager.py reset
   
   # 重启后端
   cd social_platform
   uvicorn app.main:app --reload
   
   # 重启 AI 调度器
   python -m ai_scheduler.main
   ```

3. **查看当前状态：**
   ```bash
   # 随时查看数据库状态
   python db_manager.py show-tables
   python db_manager.py show-users
   ```

## 🔧 技术细节

### 级联删除顺序

删除用户时，按以下顺序删除相关数据：
1. 点赞（`likes`）
2. 评论（`comments`）
3. 帖子（`posts`）
4. 关注关系（`follows`）
5. 用户本身（`users`）

### 数据库备份

使用 `reset` 命令时会自动备份：
- 原文件：`social_platform.db`
- 备份文件：`social_platform.db.backup`

### 数据恢复

如需恢复备份：
```bash
# 停止后端服务
# 复制备份文件
cp social_platform.db.backup social_platform.db
# 重启后端服务
```

## 📝 常见问题

### Q1: 如何只删除某个 AI 用户？
```bash
python db_manager.py delete-name 三月七
```

### Q2: 如何保留 AI 用户但清空他们的帖子？
需要手动执行 SQL：
```bash
python
>>> import sqlite3
>>> conn = sqlite3.connect('social_platform.db')
>>> conn.execute('DELETE FROM posts;')
>>> conn.execute('DELETE FROM comments;')
>>> conn.execute('DELETE FROM likes;')
>>> conn.commit()
```

### Q3: 数据库文件在哪里？
```
social_platform/social_platform.db
```

### Q4: 如何查看完整的数据库结构？
可以使用 SQLite 客户端工具（如 DB Browser for SQLite）打开 `social_platform.db` 查看。

## 🎯 最佳实践

1. **定期清理** - 开发过程中定期使用 `clean-ai` 清理测试数据
2. **备份重要** - 有重要数据时先备份再操作
3. **小心删除** - 删除操作不可逆，操作前确认
4. **查看状态** - 操作前后使用 `show-tables` 查看变化
