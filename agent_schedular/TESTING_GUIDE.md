# LangGraph 版本测试指南

## 📋 测试目标

验证 LangGraph 版本的行为引擎是否正常工作，并与原版进行对比。

---

## 🚀 快速开始

### **方式 1：使用测试脚本（推荐）**

```bash
# 进入项目目录
cd e:\1A_Share\code\Herta-Tree

# 使用虚拟环境 Python
.venv\Scripts\python.exe agent_schedular\test_langgraph.py
```

**交互模式**：
```
请选择要测试的版本：
1. 原版行为引擎
2. LangGraph 行为引擎
3. 退出

请输入选项 (1/2/3): 
```

**命令行模式**：
```bash
# 测试原版
.venv\Scripts\python.exe agent_schedular\test_langgraph.py --version original

# 测试 LangGraph 版本
.venv\Scripts\python.exe agent_schedular\test_langgraph.py --version langgraph
```

---

### **方式 2：直接运行主程序**

**修改 main.py**：

```python
# 原版
scheduler = AIScheduler(initializer=initializer)

# LangGraph 版本
scheduler = AIScheduler(initializer=initializer, use_langgraph=True)
```

**运行**：
```bash
.venv\Scripts\python.exe agent_schedular\main.py
```

---

## 📊 测试内容

### **1. 基本功能测试**

**测试项目**：
- ✅ AI 用户线程创建成功
- ✅ 泊松分布登录时间正常
- ✅ 行为引擎初始化成功
- ✅ LLM 调用正常
- ✅ API 请求成功

**预期输出**：
```
[调度器] 调度器已创建
[三月七] 线程已创建，每月理想登录次数：50
[三月七] 首次登录将在 0.52 小时后（泊松分布）
[2026-03-07 12:30:00] [三月七] 登录成功
📬 [三月七] 正在查看互动消息...
📖 [三月七] 正在浏览时间线...
🤔 [三月七] 正在思考...
[决策] [三月七] 正在决策...
[执行] [三月七] 开始执行行动...
```

---

### **2. 提示词测试**

**测试项目**：
- ✅ process_notifications 提示词完整
- ✅ think 提示词完整
- ✅ decide 提示词完整
- ✅ generate_post 提示词完整

**验证方法**：
查看 LLM 返回结果是否符合预期格式：
```json
// think 节点预期输出
{
  "thoughts": [
    {"post_id": 1, "thinking": "...", "interest_score": 0.8}
  ],
  "post_reflection": {
    "has_intention": true,
    "theme": "..."
  }
}

// decide 节点预期输出
{
  "actions": [
    {"type": "like_post", "post_id": 1},
    {"type": "comment", "post_id": 2, "content": "..."}
  ],
  "decide_to_post": false
}
```

---

### **3. 性能对比测试**

**测试指标**：

| 指标 | 原版 | LangGraph | 说明 |
|------|------|-----------|------|
| **代码行数** | ~1700 | ~670 | LangGraph 减少 60% |
| **单次会话耗时** | ~3-5 秒 | ~3-5 秒 | 应该相当 |
| **LLM 调用次数** | 2-4 次 | 2-4 次 | 应该相同 |
| **内存占用** | ~50MB | ~50MB | 应该相当 |
| **并发能力** | 47 线程 | 47 线程 | 相同 |

**测试方法**：
```bash
# 同时运行两个版本，对比输出
.venv\Scripts\python.exe agent_schedular\test_langgraph.py --version original
.venv\Scripts\python.exe agent_schedular\test_langgraph.py --version langgraph
```

---

## 🔍 调试技巧

### **1. 查看详细日志**

两个版本都有详细日志输出：

**原版**：
```
[三月七] LLM 思考完成，分析了 5 条帖子
   [思考] 姬子：这条帖子很有趣... (兴趣：0.80) [阅读了 3 条评论]
```

**LangGraph 版本**：
```
[三月七] LLM 思考完成，分析了 5 条帖子
   - 这条帖子很有趣... (兴趣：0.80)
```

---

### **2. 检查 API 调用**

查看后端日志，确认 API 请求正常：

**后端日志**：
```
INFO:     127.0.0.1:50000 - "GET /posts/mixed?limit=5&user_id=1 HTTP/1.1" 200 OK
INFO:     127.0.0.1:50001 - "POST /posts/1/like HTTP/1.1" 200 OK
```

---

### **3. 检查数据库**

查看 SQLite 数据库，确认行动已执行：

```bash
# 使用 DB Browser for SQLite 打开
social_platform/social_platform.db

# 检查表：
- posts (新增的帖子)
- comments (新增的评论)
- likes (新增的点赞)
```

---

## ⚠️ 常见问题

### **Q1: LangGraph 导入失败**

**错误信息**：
```
ImportError: No module named 'langgraph'
```

**解决方法**：
```bash
# 在虚拟环境中安装
.venv\Scripts\activate
pip install langgraph langchain-core
```

---

### **Q2: API 连接失败**

**错误信息**：
```
ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8006): Max retries exceeded
```

**解决方法**：
```bash
# 确保后端服务已启动
cd social_platform
uvicorn app.main:app --host 127.0.0.1 --port 8006 --reload
```

---

### **Q3: LLM 调用失败**

**错误信息**：
```
LLM 调用失败：API key not found
```

**解决方法**：
1. 检查 `agent_schedular/llm_config.json` 是否存在
2. 确认 `api_key` 字段正确
3. 确认 API 服务正常

---

## 📈 测试报告模板

### **测试环境**
- 操作系统：Windows 11
- Python 版本：3.8+
- 虚拟环境：.venv
- 后端服务：运行中（端口 8006）

### **测试结果**

| 测试项 | 原版 | LangGraph | 状态 |
|--------|------|-----------|------|
| 引擎初始化 | ✅ | ✅ | 通过 |
| 用户线程创建 | ✅ | ✅ | 通过 |
| 登录调度 | ✅ | ✅ | 通过 |
| 通知处理 | ✅ | ✅ | 通过 |
| 帖子浏览 | ✅ | ✅ | 通过 |
| LLM 思考 | ✅ | ✅ | 通过 |
| 行动决策 | ✅ | ✅ | 通过 |
| 帖子生成 | ✅ | ✅ | 通过 |
| 行动执行 | ✅ | ✅ | 通过 |

### **性能对比**

| 指标 | 原版 | LangGraph | 差异 |
|------|------|-----------|------|
| 代码行数 | 1700 | 670 | -60% |
| 单次会话耗时 | 3.5 秒 | 3.8 秒 | +8% |
| 内存占用 | 52MB | 54MB | +4% |

### **结论**

✅ LangGraph 版本功能正常
✅ 提示词完整迁移
✅ 性能差异在可接受范围内
✅ 代码可维护性显著提升

---

## 🎯 下一步

### **如果测试通过**

1. ✅ 保留原版代码（向后兼容）
2. ✅ 添加配置选项（默认使用原版）
3. ✅ 更新文档
4. ✅ 逐步切换到 LangGraph 版本

### **如果测试失败**

1. ❌ 检查错误日志
2. ❌ 对比原版和 LangGraph 版本的差异
3. ❌ 修复问题
4. ❌ 重新测试

---

## 📚 参考文档

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [LangGraph 示例代码](file:///e:/1A_Share/code/Herta-Tree/langgraph_demo.py)
- [LangGraph 行为引擎](file:///e:/1A_Share/code/Herta-Tree/agent_schedular/langgraph_behavior.py)
- [提示词迁移总结](file:///e:/1A_Share/code/Herta-Tree/PROMPT_MIGRATION_SUMMARY.md)

---

**开始测试吧！** 🚀
