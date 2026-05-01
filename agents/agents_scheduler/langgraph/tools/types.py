# LangChain/LangGraph 工具集模块
# 错误类型和结果类型定义

from typing import Dict, Any, TypedDict


# ==================== 工具函数错误类型 ====================

class ToolExecutionError(Exception):
    """工具执行错误基类"""
    pass


class AuthenticationError(ToolExecutionError):
    """认证错误"""
    pass


class NotFoundError(ToolExecutionError):
    """资源不存在错误"""
    pass


class ValidationError(ToolExecutionError):
    """参数验证错误"""
    pass


class UnauthorizedError(ToolExecutionError):
    """未授权错误，Token 不存在或已过期"""
    pass


# ==================== 统一工具返回值结构 ====================

class ToolResult(TypedDict):
    """
    统一工具返回值结构

    所有 @tool 装饰的函数都应返回此结构。

    设计要点：
    - action: 自然语言格式的动作描述，描述"你做了什么"
    - data: 工具返回的原始数据，供 LLM 下次决策使用

    Example:
        return ToolResult(
            action="点赞了 @景元 的帖子：今天入手了新角色...",
            data={"post": {...}, "comments": [...]}
        )
    """
    action: str                              # 自然语言格式的动作描述
    data: Dict[str, Any]                     # 工具返回的原始数据
