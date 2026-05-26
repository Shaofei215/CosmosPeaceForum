"""
Management Database Client - 数据库抽象层
供 agents 模块从 management 数据库读取配置

此模块是 agents 与 management 数据库之间的桥梁，
使 agents_scheduler 各模块（config.py、langgraph/config.py、memory/config.py 等）
能够通过统一的 API 从管理数据库读取配置。
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from agents.management.backend.core.config import get_config


def _get_db_path() -> str:
    """获取管理数据库路径"""
    return get_config().get_db_path()


class ManagementDBClient:
    """
    管理数据库客户端
    
    提供从 management.db 读取配置的接口，
    供 scheduler 各模块调用。
    """
    
    def __init__(self, db_path: str = None):
        """
        初始化数据库客户端
        
        Args:
            db_path: 数据库文件路径（可选，默认从环境变量或默认路径获取）
        """
        self._db_path = db_path or _get_db_path()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_system_config(self, key: str, default: str = "") -> str:
        """
        获取系统配置值
        
        Args:
            key: 配置键
            default: 默认值（数据库不存在时使用）
            
        Returns:
            str: 配置值
        """
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT value FROM system_configs WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                return row["value"] if row else default
            finally:
                conn.close()
        except Exception:
            return default
    
    def get_all_system_configs(self) -> dict:
        """
        获取所有系统配置
        
        Returns:
            dict: {key: value} 字典
        """
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute("SELECT key, value FROM system_configs")
                return {row["key"]: row["value"] for row in cursor.fetchall()}
            finally:
                conn.close()
        except Exception:
            return {}

    def get_prompt_config(self, key: str, default: str = "") -> str:
        """
        获取可编辑提示词配置。

        Args:
            key: 提示词配置键
            default: 表或记录不存在时使用的默认值

        Returns:
            str: 提示词模板文本
        """
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT value, default_value FROM prompt_configs WHERE key = ?",
                    (key,),
                )
                row = cursor.fetchone()
                if not row:
                    return default
                if row["value"] == row["default_value"] and row["default_value"] != default:
                    return default
                return row["value"]
            finally:
                conn.close()
        except Exception:
            return default
    
    def _parse_knows_ids(self, raw_value: str) -> list:
        """解析 knows_ids JSON 字符串"""
        try:
            return json.loads(raw_value)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_agent_configs(self) -> list:
        """
        获取所有启用的 Agent 配置
        
        Returns:
            list[dict]: Agent 配置列表
        """
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT * FROM agent_configs WHERE is_active = 1 ORDER BY id"
                )
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    agent = dict(row)
                    agent["knows_ids"] = self._parse_knows_ids(agent.get("knows_ids", "[]"))
                    result.append(agent)
                return result
            finally:
                conn.close()
        except Exception:
            return []
    
    def get_agent_config(self, agent_id: int) -> Optional[dict]:
        """
        获取单个 Agent 配置
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Optional[dict]: Agent 配置字典
        """
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT * FROM agent_configs WHERE id = ?",
                    (agent_id,)
                )
                row = cursor.fetchone()
                if row:
                    agent = dict(row)
                    agent["knows_ids"] = self._parse_knows_ids(agent.get("knows_ids", "[]"))
                    return agent
                return None
            finally:
                conn.close()
        except Exception:
            return None

    def get_agent_login_stats(self, agent_id: int) -> dict:
        """Return persisted login stats for an Agent config."""
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    """
                    SELECT total_login_count, last_login_timestamp, last_login_at
                    FROM agent_configs
                    WHERE id = ?
                    """,
                    (agent_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return {
                        "total_login_count": 0,
                        "last_login_timestamp": None,
                        "last_login_at": None,
                    }
                return {
                    "total_login_count": row["total_login_count"] or 0,
                    "last_login_timestamp": row["last_login_timestamp"],
                    "last_login_at": row["last_login_at"],
                }
            finally:
                conn.close()
        except Exception:
            return {
                "total_login_count": 0,
                "last_login_timestamp": None,
                "last_login_at": None,
            }

    def record_agent_login(
        self,
        agent_id: int,
        scaled_timestamp: float | None = None,
        login_at: datetime | None = None,
    ) -> dict:
        """Record one successful Agent login and return stats for prompt injection."""
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    """
                    SELECT total_login_count, last_login_timestamp, last_login_at
                    FROM agent_configs
                    WHERE id = ?
                    """,
                    (agent_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return {
                        "total_login_count": 0,
                        "previous_last_login_timestamp": None,
                        "last_login_timestamp": scaled_timestamp,
                        "last_login_at": None,
                    }

                previous_count = row["total_login_count"] or 0
                previous_timestamp = row["last_login_timestamp"]
                timestamp = (login_at or datetime.utcnow()).isoformat(sep=" ")
                new_count = previous_count + 1

                update_columns = [
                    "last_login_at = ?",
                    "total_login_count = ?",
                    "updated_at = ?",
                ]
                values: list = [timestamp, new_count, timestamp]
                if scaled_timestamp is not None:
                    update_columns.append("last_login_timestamp = ?")
                    values.append(scaled_timestamp)
                values.append(agent_id)

                conn.execute(
                    f"UPDATE agent_configs SET {', '.join(update_columns)} WHERE id = ?",
                    values,
                )
                conn.commit()
                return {
                    "total_login_count": new_count,
                    "previous_last_login_timestamp": previous_timestamp,
                    "last_login_timestamp": scaled_timestamp,
                    "last_login_at": timestamp,
                }
            finally:
                conn.close()
        except Exception:
            return {
                "total_login_count": 0,
                "previous_last_login_timestamp": None,
                "last_login_timestamp": scaled_timestamp,
                "last_login_at": None,
            }

    def update_agent_last_login(self, agent_id: int, login_at: datetime | None = None) -> bool:
        """记录 Agent 最近一次成功登录时间。"""
        result = self.record_agent_login(agent_id=agent_id, login_at=login_at)
        return result.get("total_login_count", 0) > 0
    
    def get_active_model_configs(self) -> list:
        """
        获取所有启用的模型配置
        
        Returns:
            list[dict]: 模型配置列表
        """
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT * FROM model_configs WHERE is_active = 1 ORDER BY id"
                )
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()
        except Exception:
            return []
    
    def get_model_config(self, model_id: int) -> Optional[dict]:
        """
        获取单个模型配置
        
        Args:
            model_id: 模型配置 ID
            
        Returns:
            Optional[dict]: 模型配置字典
        """
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT * FROM model_configs WHERE id = ?",
                    (model_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()
        except Exception:
            return None

    def get_active_embedding_config(self) -> Optional[dict]:
        """
        获取启用的 Embedding 配置
        
        Returns:
            Optional[dict]: Embedding 配置字典
        """
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT * FROM embedding_configs WHERE is_active = 1 LIMIT 1"
                )
                row = cursor.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()
        except Exception:
            return None


_db_client = None

def get_db_client() -> ManagementDBClient:
    """获取数据库客户端单例"""
    global _db_client
    if _db_client is None:
        _db_client = ManagementDBClient()
    return _db_client
