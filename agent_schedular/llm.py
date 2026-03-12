"""
LLM 客户端模块
提供与硅基流动 API 的交互功能
增强版：支持 JSON 智能修复和 LLM 自我修复重试机制
"""

import json
import re
import requests
import time
from pathlib import Path
from typing import Optional, Any, Tuple, List


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
        self.timeout = self.config.get("timeout", 60)  # 默认 60 秒超时
        self.max_retries = self.config.get("max_retries", 3)  # HTTP 请求重试次数
        self.json_retry_count = self.config.get("json_retry_count", 3)  # JSON 修复重试次数

    # ==================== 配置加载 ====================

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

    # ==================== JSON 修复工具方法 ====================

    @staticmethod
    def _remove_markdown_fences(content: str) -> str:
        """
        移除 markdown 代码块标记
        
        参数:
            content: 原始内容
            
        返回:
            清理后的内容
        """
        cleaned = content.strip()
        
        # 移除 ```json 或 ``` 开头
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        
        # 移除 ``` 结尾
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        
        return cleaned.strip()

    @staticmethod
    def _fix_trailing_commas(content: str) -> str:
        """
        修复尾随逗号（JSON 标准不允许）
        
        参数:
            content: 原始内容
            
        返回:
            修复后的内容
        """
        # 移除 } 或 ] 前面的逗号
        content = re.sub(r',\s*}', '}', content)
        content = re.sub(r',\s*]', ']', content)
        return content

    @staticmethod
    def _fix_missing_commas(content: str) -> str:
        """
        修复缺失的逗号
        
        参数:
            content: 原始内容
            
        返回:
            修复后的内容
        """
        # 修复 }{ 之间缺失的逗号
        content = re.sub(r'}\s*{', '},{', content)
        # 修复 ]{ 之间缺失的逗号
        content = re.sub(r']\s*{', '],{', content)
        # 修复 }[ 之间缺失的逗号
        content = re.sub(r'}\s*\[', '},[', content)
        return content

    @staticmethod
    def _fix_single_quotes(content: str) -> str:
        """
        将单引号替换为双引号（JSON 标准要求双引号）
        
        参数:
            content: 原始内容
            
        返回:
            修复后的内容
        """
        return content.replace("'", '"')

    def _auto_fix_json(self, content: str) -> Tuple[str, List[str]]:
        """
        自动修复常见的 JSON 错误
        
        参数:
            content: 原始内容
            
        返回:
            (修复后的内容，修复记录列表)
        """
        fixes_applied = []
        original = content
        
        # 1. 移除 markdown 代码块标记
        content = self._remove_markdown_fences(content)
        if content != original:
            fixes_applied.append("移除了 markdown 代码块标记")
            original = content
        
        # 2. 修复尾随逗号
        content = self._fix_trailing_commas(content)
        if content != original:
            fixes_applied.append("修复了尾随逗号")
            original = content
        
        # 3. 修复缺失的逗号
        content = self._fix_missing_commas(content)
        if content != original:
            fixes_applied.append("修复了缺失的逗号")
            original = content
        
        # 4. 尝试修复单引号
        content = self._fix_single_quotes(content)
        if content != original:
            fixes_applied.append("将单引号替换为双引号")
        
        return content, fixes_applied

    def _try_parse_json(self, content: str) -> Tuple[bool, Any, str]:
        """
        尝试解析 JSON（基础解析，不带 LLM 重试）
        
        参数:
            content: 要解析的内容
            
        返回:
            (是否成功，解析结果，错误信息)
        """
        try:
            result = json.loads(content)
            return True, result, ""
        except json.JSONDecodeError as e:
            return False, None, str(e)

    # ==================== HTTP 请求方法 ====================

    def send_request(self, prompt: str, system_prompt: Optional[str] = None) -> dict:
        """
        向 LLM API 发送请求并获取响应（带 HTTP 重试机制）

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

        # HTTP 重试机制
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout as e:
                last_exception = e
                print(f"[LLM] 请求超时 (尝试 {attempt + 1}/{self.max_retries})，{self.timeout}秒后重试...")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
            except requests.exceptions.RequestException as e:
                last_exception = e
                print(f"[LLM] 请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
        
        # 所有重试都失败
        raise last_exception

    # ==================== JSON 解析与 LLM 自我修复 ====================

    def _fix_json_with_llm(self, invalid_content: str, error_message: str, 
                           original_prompt: str, original_system_prompt: Optional[str],
                           attempt: int = 1) -> dict:
        """
        使用 LLM 自我修复 JSON：将无效的 JSON 再次发给 LLM，让它修复
        
        参数:
            invalid_content: LLM 返回的无效 JSON 内容
            error_message: JSON 解析错误信息
            original_prompt: 原始提示词
            original_system_prompt: 原始系统提示词
            attempt: 当前重试次数
            
        返回:
            修复后的 JSON 对象
        """
        if attempt > self.json_retry_count:
            print(f"[LLM] ❌ 超过最大 JSON 修复重试次数 ({self.json_retry_count})")
            return {
                "raw_content": invalid_content,
                "parse_error": f"超过最大修复重试次数：{error_message}",
                "success": False
            }
        
        print(f"\n[LLM] 🔧 JSON 解析失败，尝试让 LLM 自我修复 (第 {attempt}/{self.json_retry_count} 次)...")
        print(f"[LLM] 错误信息：{error_message}")
        
        # 构建修复提示词
        fix_prompt = f"""你是一个 JSON 修复助手。你之前生成的 JSON 格式有误，无法解析。

【原始任务】
{original_prompt}

【你返回的内容】
{invalid_content[:2000]}  # 只取前 2000 字符

【错误信息】
{error_message}

【你的任务】
请修复上述内容中的 JSON 格式错误，使其能够被正确解析。
注意：
1. 只输出修复后的 JSON，不要包含任何解释
2. 确保所有字符串使用双引号
3. 确保没有尾随逗号
4. 确保括号匹配
5. 保持原始内容的语义不变

请直接输出修复后的 JSON："""
        
        # 使用简单的系统提示
        fix_system_prompt = "你是一个 JSON 修复专家，只输出合法的 JSON 格式，不要包含任何 markdown 标记或解释。"
        
        try:
            # 调用 LLM 进行修复
            response = self.send_request(fix_prompt, fix_system_prompt)
            content = response["choices"][0]["message"]["content"]
            
            # 尝试解析修复后的内容
            success, result, error = self._try_parse_json(content)
            
            if success:
                print(f"[LLM] ✅ LLM 自我修复成功！")
                # 确保返回的是字典类型
                if isinstance(result, dict):
                    return result
                elif isinstance(result, list):
                    return {"data": result}
                else:
                    return {"result": result}
            else:
                # 修复后仍然失败，继续重试
                print(f"[LLM] ⚠️ LLM 修复后仍然无法解析：{error}")
                return self._fix_json_with_llm(
                    content,  # 使用新的内容继续修复
                    error,
                    original_prompt,
                    original_system_prompt,
                    attempt + 1
                )
                
        except Exception as e:
            print(f"[LLM] ⚠️ LLM 修复请求失败：{e}")
            # 如果是 HTTP 错误，也计入重试次数
            return self._fix_json_with_llm(
                invalid_content,
                f"修复请求失败：{str(e)}",
                original_prompt,
                original_system_prompt,
                attempt + 1
            )

    def parse_response(self, response: dict, 
                      original_prompt: Optional[str] = None,
                      original_system_prompt: Optional[str] = None) -> dict:
        """
        解析 LLM 返回的 JSON 响应（增强版：带 LLM 自我修复机制）

        参数:
            response: API 返回的 JSON 字典
            original_prompt: 原始提示词（用于 LLM 自我修复）
            original_system_prompt: 原始系统提示词（用于 LLM 自我修复）

        返回:
            解析后的 JSON 对象字典
        """
        content = response["choices"][0]["message"]["content"]
        
        print(f"[LLM] 开始解析响应内容...")
        
        # 步骤 1：尝试直接解析
        success, result, error = self._try_parse_json(content)
        
        if success:
            print(f"[LLM] ✅ JSON 解析成功")
            # 确保返回的是字典类型
            if isinstance(result, dict):
                return result
            elif isinstance(result, list):
                return {"data": result}
            else:
                return {"result": result}
        
        # 步骤 2：尝试自动修复（不使用 LLM）
        print(f"[LLM] ⚠️ JSON 解析失败，尝试自动修复：{error}")
        fixed_content, fixes = self._auto_fix_json(content)
        
        if fixes:
            print(f"[LLM] 应用修复：{', '.join(fixes)}")
        
        success, result, error = self._try_parse_json(fixed_content)
        
        if success:
            print(f"[LLM] ✅ 自动修复成功！")
            if isinstance(result, dict):
                return result
            elif isinstance(result, list):
                return {"data": result}
            else:
                return {"result": result}
        
        # 步骤 3：使用 LLM 自我修复（需要原始提示词）
        if original_prompt:
            return self._fix_json_with_llm(
                content,
                error,
                original_prompt,
                original_system_prompt,
                attempt=1
            )
        else:
            # 没有原始提示词，无法进行 LLM 自我修复
            print(f"[LLM] ❌ 自动修复失败，且缺少原始提示词，无法进行 LLM 自我修复")
            print(f"[LLM] 原始内容预览：{content[:200]}...")
            return {
                "raw_content": content,
                "parse_error": error,
                "success": False
            }

    # ==================== 主接口方法 ====================

    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> dict:
        """
        完整的聊天流程：发送请求并解析响应（支持 LLM 自我修复）

        参数:
            prompt: 用户输入的提示词
            system_prompt: 可选的系统提示词

        返回:
            解析后的 JSON 对象字典
        """
        response = self.send_request(prompt, system_prompt)
        # 传递原始提示词，以便在 JSON 解析失败时进行 LLM 自我修复
        return self.parse_response(response, prompt, system_prompt)


if __name__ == "__main__":
    # 测试代码
    client = LLMClient()
    
    print("="*60)
    print("测试 1：正常 JSON 生成")
    print("="*60)
    test_prompt = "请生成一个包含姓名、年龄和城市的 JSON 对象"
    test_system_prompt = "你只能输出 JSON 格式的数据"
    result = client.chat(test_prompt, test_system_prompt)
    print(f"\n结果：{result}")
    print(f"类型：{type(result)}\n")
    
    print("="*60)
    print("测试 2：测试 LLM 自我修复（模拟错误 JSON）")
    print("="*60)
    # 这个测试会故意让 LLM 生成有问题的 JSON，然后测试自我修复
    test_prompt2 = """请生成一个复杂的 JSON 对象，包含：
1. 一个用户列表，每个用户有姓名、年龄、邮箱
2. 一个产品列表，每个产品有名称、价格、库存
3. 一个订单列表，每个订单有用户 ID、产品 ID、数量

注意：这是一个测试，请尽量生成复杂的嵌套结构。"""
    result2 = client.chat(test_prompt2, test_system_prompt)
    print(f"\n结果：{result2}")
