# LLM 客户端使用指南

## 快速开始

### 1. 安装依赖

```bash
pip install openai
```

### 2. 配置 LLM

复制示例配置文件：

```bash
cd agent_schedular
copy llm_config.example.json llm_config.json
```

编辑 `llm_config.json`：

```json
{
  "api_key": "sk-your-actual-api-key",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-3.5-turbo",
  "timeout": 30,
  "max_tokens": 1000,
  "temperature": 0.7
}
```

**配置说明：**
- `api_key`: 你的 API 密钥
- `base_url`: API 基础 URL（可选，使用默认值可不填）
- `model`: 模型名称
- `timeout`: 请求超时时间（秒）
- `max_tokens`: 最大生成 token 数
- `temperature`: 温度（0-1，越高越随机）

### 3. 使用 LLM 客户端

#### 方法 1: 使用类

```python
from agent_schedular.llm import LLMClient, LLMConfig

# 创建配置
config = LLMConfig("llm_config.json")

# 创建客户端
client = LLMClient(config)

# 检查是否可用
if client.is_available():
    # 带系统提示的聊天
    response = client.chat_with_system(
        system_prompt="你是一个助手。",
        user_message="你好！"
    )
    print(response)
    
    # 普通聊天
    messages = [
        {"role": "user", "content": "你好"}
    ]
    response = client.chat(messages)
    print(response)
```

#### 方法 2: 使用快捷函数

```python
from agent_schedular.llm import chat

# 快捷调用
response = chat(
    system_prompt="你是一个助手。",
    user_message="你好！"
)
print(response)
```

#### 方法 3: 使用模块导入

```python
from agent_schedular import chat, create_client

# 方法 1: 快捷函数
response = chat("你是助手。", "你好！")

# 方法 2: 创建客户端
client = create_client()
response = client.chat_with_system("你是助手。", "你好！")
```

## 代码结构

### LLMConfig 类

配置管理类：
- `load_config()`: 从文件加载配置
- `save_config()`: 保存配置到文件
- 配置项：api_key, base_url, model, timeout, max_tokens, temperature

### LLMClient 类

LLM 客户端类：
- `chat(messages, ...)`: 发送聊天请求
- `chat_with_system(system_prompt, user_message, ...)`: 带系统提示的聊天
- `is_available()`: 检查客户端是否可用

### 快捷函数

- `create_client(config_path)`: 创建客户端实例
- `chat(system_prompt, user_message, config_path)`: 快捷聊天函数

## 使用示例

### 示例 1: AI 用户发帖

```python
from agent_schedular.llm import LLMClient

client = LLMClient()

# 根据 AI 人设生成帖子
user_config = {
    "username": "三月七",
    "personality_prompt": "你是开朗活泼的三月七..."
}

response = client.chat_with_system(
    system_prompt=user_config["personality_prompt"],
    user_message="请发布一条关于今天心情的动态"
)

if response:
    print(f"{user_config['username']} 发布了：{response}")
```

### 示例 2: 回复评论

```python
# 生成回复
reply = client.chat_with_system(
    system_prompt="你是三月七，请用你的语气回复",
    user_message="有人评论：你的照片真好看！"
)

print(f"回复：{reply}")
```

### 示例 3: 批量处理

```python
from agent_schedular import create_client

client = create_client()

prompts = [
    ("你是助手", "今天天气如何？"),
    ("你是诗人", "写一首关于春天的诗"),
    ("你是程序员", "Python 和 Java 哪个更好？")
]

for system, user in prompts:
    response = client.chat_with_system(system, user)
    print(f"{system}: {response}\n")
```

## 错误处理

```python
from agent_schedular.llm import LLMClient

client = LLMClient()

if not client.is_available():
    print("LLM 不可用，使用默认回复")
    response = "默认回复内容"
else:
    response = client.chat_with_system("你是助手", "你好")
    if not response:
        response = "调用失败，使用默认回复"
```

## 注意事项

1. **配置文件**：首次使用需创建 `llm_config.json`
2. **API Key**：妥善保管，不要提交到版本控制
3. **错误处理**：始终检查返回值是否为 None
4. **速率限制**：注意 API 调用频率限制
5. **Token 消耗**：合理设置 max_tokens 控制成本

## 测试

运行测试：

```bash
cd agent_schedular
python llm.py
```

如果配置正确，将看到 LLM 的回复。
