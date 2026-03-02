"""
LLM 客户端模块
提供与硅基流动 API 的交互功能
"""

import json
import requests
from pathlib import Path
from typing import Optional


class LLMClient:
    """LLM 客户端类，用于与硅基流动 API 进行交互"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 LLM 客户端

        参数:
            config_path: 配置文件路径，默认为当前目录下的 llm_config.json
        """
        if config_path is None:
            config_path = Path(__file__).parent / "llm_config.json"

        self.config = self._load_config(config_path)
        self.api_key = self.config.get("api_key")
        self.model = self.config.get("llm_model")
        self.api_url = self.config.get("api_url")
        self.max_tokens = self.config.get("max_tokens", 2048)
        self.temperature = self.config.get("temperature", 0.7)

    def _load_config(self, config_path: Path) -> dict:
        """
        加载 LLM 配置文件

        参数:
            config_path: 配置文件路径

        返回:
            配置字典
        """
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def send_request(self, prompt: str, system_prompt: Optional[str] = None) -> dict:
        """
        向 LLM API 发送请求并获取响应

        参数:
            prompt: 用户输入的提示词
            system_prompt: 可选的系统提示词

        返回:
            API 返回的 JSON 响应字典
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        messages.append({
            "role": "user",
            "content": prompt
        })

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"}
        }

        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=30
        )

        response.raise_for_status()
        return response.json()

    def parse_response(self, response: dict) -> dict:
        """
        解析 LLM 返回的 JSON 响应

        参数:
            response: API 返回的 JSON 字典

        返回:
            解析后的 JSON 对象字典
        """
        content = response["choices"][0]["message"]["content"]
        return json.loads(content)

    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> dict:
        """
        完整的聊天流程：发送请求并解析响应

        参数:
            prompt: 用户输入的提示词
            system_prompt: 可选的系统提示词

        返回:
            解析后的 JSON 对象字典
        """
        response = self.send_request(prompt, system_prompt)
        return self.parse_response(response)


if __name__ == "__main__":
    client = LLMClient()
    test_prompt = "请生成一个包含姓名、年龄和城市的 JSON 对象"
    test_system_prompt = "你只能输出 JSON 格式的数据"
    result = client.chat(test_prompt, test_system_prompt)
    print(f"用户：{test_prompt}")
    print(f"助手：{result}")
    print(f"类型：{type(result)}")
