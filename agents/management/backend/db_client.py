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
from agents.management.backend.core.timezone import local_now
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
    
    def __init__(self, db_path: Optional[str] = None):
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

    def get_scheduler_time_state(self) -> Optional[dict]:
        """
        读取 Scheduler 缩放时间持久化锚点。

        Returns:
            Optional[dict]: 锚点字段字典；表或记录尚不存在时返回 ``None``。
        """
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    """
                    SELECT scaled_timestamp, real_timestamp, scale,
                           offset_seconds, paused
                    FROM scheduler_time_state
                    WHERE id = 1
                    """
                )
                row = cursor.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()
        except (sqlite3.Error, ValueError, TypeError):
            return None

    def save_scheduler_time_state(
        self,
        scaled_timestamp: float,
        real_timestamp: float,
        scale: float,
        offset_seconds: int,
        paused: bool,
    ) -> bool:
        """
        原子写入 Scheduler 缩放时间持久化锚点。

        Args:
            scaled_timestamp: 锚点对应的缩放时间戳。
            real_timestamp: 写入锚点时的真实 Unix 时间戳。
            scale: 锚点之后使用的时间倍率。
            offset_seconds: 当前显式时间偏移秒数。
            paused: 时间轴是否暂停。

        Returns:
            bool: 写入成功时返回 ``True``；数据库尚未迁移或写入失败时返回 ``False``。
        """
        try:
            conn = self._get_connection()
            try:
                updated_at = local_now().isoformat(sep=" ")
                conn.execute(
                    """
                    INSERT INTO scheduler_time_state (
                        id, scaled_timestamp, real_timestamp, scale,
                        offset_seconds, paused, updated_at
                    )
                    VALUES (1, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        scaled_timestamp = excluded.scaled_timestamp,
                        real_timestamp = excluded.real_timestamp,
                        scale = excluded.scale,
                        offset_seconds = excluded.offset_seconds,
                        paused = excluded.paused,
                        updated_at = excluded.updated_at
                    """,
                    (
                        scaled_timestamp,
                        real_timestamp,
                        scale,
                        offset_seconds,
                        paused,
                        updated_at,
                    ),
                )
                conn.commit()
                return True
            finally:
                conn.close()
        except (sqlite3.Error, ValueError, TypeError):
            return False

    def get_latest_agent_login_timestamp(self) -> float:
        """
        获取历史 Agent 排程中最大的缩放登录时间戳。

        该值仅用于首次建立 Scheduler 时间锚点时承接旧版本数据；后续启动以
        ``scheduler_time_state`` 为准。

        Returns:
            float: 最大登录时间戳；表、记录或合法值不存在时返回 ``0.0``。
        """
        try:
            conn = self._get_connection()
            try:
                row = conn.execute(
                    "SELECT MAX(last_login_timestamp) AS latest FROM agent_configs"
                ).fetchone()
                return float(row["latest"] or 0.0) if row else 0.0
            finally:
                conn.close()
        except (sqlite3.Error, ValueError, TypeError):
            return 0.0

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
        获取全部 Agent 配置。
        
        Returns:
            list[dict]: Agent 配置列表
        """
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute("SELECT * FROM agent_configs ORDER BY id")
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

    def get_short_term_memory(self, agent_id: int) -> dict:
        """读取内部角色当前的短期记忆快照。

        Args:
            agent_id: Management 中的角色配置 ID。

        Returns:
            dict: 当前 Markdown、revision、缩放更新时间和更新时登录次数。记录或表
            尚不存在时返回显式空状态。
        """

        empty = {
            "content": "",
            "revision": 0,
            "updated_at": None,
            "updated_login_count": 0,
        }
        try:
            conn = self._get_connection()
            try:
                row = conn.execute(
                    """
                    SELECT content, revision, updated_at, updated_login_count
                    FROM short_term_memories
                    WHERE id = ?
                    """,
                    (agent_id,),
                ).fetchone()
                return dict(row) if row else empty
            finally:
                conn.close()
        except (sqlite3.Error, ValueError, TypeError):
            return empty

    def update_short_term_memory(
        self,
        agent_id: int,
        content: str,
        updated_at: float,
    ) -> Optional[dict]:
        """原子覆盖内部角色短期记忆并递增 revision。

        Args:
            agent_id: Management 中的角色配置 ID。
            content: 保存后的完整 Markdown；空字符串表示清空。
            updated_at: 编辑发生时的 Scheduler 缩放时间戳。

        Returns:
            Optional[dict]: 新版本元数据；角色、表不存在或写入失败时返回 ``None``。
        """

        try:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                agent = conn.execute(
                    "SELECT total_login_count FROM agent_configs WHERE id = ?",
                    (agent_id,),
                ).fetchone()
                if agent is None:
                    conn.rollback()
                    return None

                current = conn.execute(
                    "SELECT revision FROM short_term_memories WHERE id = ?",
                    (agent_id,),
                ).fetchone()
                updated_login_count = max(0, int(agent["total_login_count"] or 0))
                if current is None:
                    revision = 1
                    conn.execute(
                        """
                        INSERT INTO short_term_memories (
                            id, content, revision, updated_at, updated_login_count
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            agent_id,
                            content,
                            revision,
                            float(updated_at),
                            updated_login_count,
                        ),
                    )
                else:
                    revision = int(current["revision"]) + 1
                    conn.execute(
                        """
                        UPDATE short_term_memories
                        SET content = ?, revision = ?, updated_at = ?,
                            updated_login_count = ?
                        WHERE id = ?
                        """,
                        (
                            content,
                            revision,
                            float(updated_at),
                            updated_login_count,
                            agent_id,
                        ),
                    )
                conn.commit()
                return {
                    "success": True,
                    "revision": revision,
                    "updated_at": float(updated_at),
                    "updated_login_count": updated_login_count,
                }
            finally:
                conn.close()
        except (sqlite3.Error, ValueError, TypeError):
            return None

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
                timestamp = (login_at or local_now()).isoformat(sep=" ")
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

    def update_agent_profile(
        self,
        agent_id: int,
        social_platform_user_id: int,
        username: str,
        personal_signature: str,
    ) -> bool:
        """原子更新内部 Agent 的公开资料镜像。

        仅当 Agent 配置 ID 与公开平台用户 ID 同时匹配时才写入，防止线程上下文
        或账号映射异常时修改错误角色。

        Args:
            agent_id: management 中的 Agent 配置 ID。
            social_platform_user_id: 当前登录的公开平台用户 ID。
            username: 公开平台已确认的新用户名。
            personal_signature: 公开平台已确认的新个人签名。

        Returns:
            bool: 成功更新唯一一条配置时返回 ``True``，否则返回 ``False``。
        """

        try:
            conn = self._get_connection()
            try:
                updated_at = local_now().isoformat(sep=" ")
                cursor = conn.execute(
                    """
                    UPDATE agent_configs
                    SET username = ?, personal_signature = ?, updated_at = ?
                    WHERE id = ? AND social_platform_user_id = ?
                    """,
                    (
                        username,
                        personal_signature,
                        updated_at,
                        agent_id,
                        social_platform_user_id,
                    ),
                )
                if cursor.rowcount != 1:
                    conn.rollback()
                    return False
                conn.commit()
                return True
            finally:
                conn.close()
        except (sqlite3.Error, ValueError, TypeError):
            return False
    
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
