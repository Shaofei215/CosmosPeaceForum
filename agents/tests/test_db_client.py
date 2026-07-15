import pytest
from unittest.mock import patch, MagicMock
import json
import sqlite3
import tempfile
import os

from agents.management.backend.db_client import ManagementDBClient, get_db_client


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_configs (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_configs (
            id INTEGER PRIMARY KEY,
            username TEXT,
            name TEXT,
            is_active INTEGER DEFAULT 1,
            knows_ids TEXT DEFAULT '[]',
            personality_prompt TEXT,
            personal_signature TEXT,
            social_platform_user_id TEXT,
            monthly_logins INTEGER DEFAULT 30,
            last_login_at DATETIME,
            last_login_timestamp REAL,
            total_login_count INTEGER DEFAULT 0,
            updated_at DATETIME
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_configs (
            id INTEGER PRIMARY KEY,
            provider TEXT,
            model_name TEXT,
            api_key TEXT,
            base_url TEXT,
            temperature REAL,
            is_active INTEGER DEFAULT 1
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS embedding_configs (
            id INTEGER PRIMARY KEY,
            base_url TEXT,
            api_key TEXT,
            model_name TEXT,
            dimension INTEGER,
            is_active INTEGER DEFAULT 0
        )
    """)

    cursor.execute("INSERT INTO system_configs (key, value) VALUES (?, ?)", ("TEST_KEY", "test_value"))
    cursor.execute(
        "INSERT INTO agent_configs (id, username, name, is_active, knows_ids) VALUES (?, ?, ?, ?, ?)",
        (1, "test_user", "Test", 1, '[2, 3]')
    )
    cursor.execute(
        "INSERT INTO model_configs (id, provider, model_name, api_key, is_active, temperature) VALUES (?, ?, ?, ?, ?, ?)",
        (1, "openai", "gpt-4", "test_key", 1, 1.0)
    )
    cursor.execute(
        "INSERT INTO embedding_configs (id, base_url, api_key, model_name, dimension, is_active) VALUES (?, ?, ?, ?, ?, ?)",
        (1, "https://test.api/v1", "emb_key", "text-embedding-3-small", 1536, 1)
    )

    conn.commit()
    conn.close()

    yield db_path

    if os.path.exists(db_path):
        os.remove(db_path)


class TestManagementDBClient:
    def test_get_system_config(self, temp_db):
        client = ManagementDBClient(db_path=temp_db)
        result = client.get_system_config("TEST_KEY")
        assert result == "test_value"

    def test_get_system_config_default(self, temp_db):
        client = ManagementDBClient(db_path=temp_db)
        result = client.get_system_config("NONEXISTENT_KEY", "default")
        assert result == "default"

    def test_get_all_system_configs(self, temp_db):
        client = ManagementDBClient(db_path=temp_db)
        result = client.get_all_system_configs()
        assert isinstance(result, dict)
        assert "TEST_KEY" in result

    def test_get_agent_configs(self, temp_db):
        client = ManagementDBClient(db_path=temp_db)
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO agent_configs (id, username, name, is_active) VALUES (?, ?, ?, ?)",
            (2, "inactive_user", "Inactive", 0),
        )
        conn.commit()
        conn.close()

        result = client.get_agent_configs()
        assert isinstance(result, list)
        assert len(result) == 2
        assert "knows_ids" in result[0]
        assert isinstance(result[0]["knows_ids"], list)

    def test_get_agent_config(self, temp_db):
        client = ManagementDBClient(db_path=temp_db)
        result = client.get_agent_config(1)
        assert result is not None
        assert result["username"] == "test_user"
        assert result["knows_ids"] == [2, 3]

    def test_get_agent_config_not_found(self, temp_db):
        client = ManagementDBClient(db_path=temp_db)
        result = client.get_agent_config(999)
        assert result is None

    def test_record_agent_login_updates_stats_columns(self, temp_db):
        client = ManagementDBClient(db_path=temp_db)
        result = client.record_agent_login(1, scaled_timestamp=120.0)

        assert result["total_login_count"] == 1
        assert result["previous_last_login_timestamp"] is None
        assert result["last_login_timestamp"] == 120.0

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT total_login_count, last_login_timestamp FROM agent_configs WHERE id = 1"
        ).fetchone()
        conn.close()

        assert row["total_login_count"] == 1
        assert row["last_login_timestamp"] == 120.0

    def test_record_agent_login_returns_previous_timestamp(self, temp_db):
        client = ManagementDBClient(db_path=temp_db)
        client.record_agent_login(1, scaled_timestamp=120.0)
        result = client.record_agent_login(1, scaled_timestamp=360.0)

        assert result["total_login_count"] == 2
        assert result["previous_last_login_timestamp"] == 120.0
        assert result["last_login_timestamp"] == 360.0

    def test_get_agent_login_stats_defaults(self, temp_db):
        client = ManagementDBClient(db_path=temp_db)
        result = client.get_agent_login_stats(1)

        assert result["total_login_count"] == 0
        assert result["last_login_timestamp"] is None

    def test_update_agent_profile_requires_matching_platform_user(self, temp_db: str) -> None:
        """资料镜像只允许由匹配的公开平台账号更新。"""

        conn = sqlite3.connect(temp_db)
        conn.execute(
            "UPDATE agent_configs SET social_platform_user_id = ?, personal_signature = ? WHERE id = 1",
            (42, "old signature"),
        )
        conn.commit()
        conn.close()
        client = ManagementDBClient(db_path=temp_db)

        assert client.update_agent_profile(1, 999, "wrong", "wrong") is False
        assert client.update_agent_profile(1, 42, "new_name", "new signature") is True
        updated = client.get_agent_config(1)
        assert updated["username"] == "new_name"
        assert updated["personal_signature"] == "new signature"

    def test_get_active_model_configs(self, temp_db):
        client = ManagementDBClient(db_path=temp_db)
        result = client.get_active_model_configs()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_model_config(self, temp_db):
        client = ManagementDBClient(db_path=temp_db)
        result = client.get_model_config(1)
        assert result is not None
        assert result["provider"] == "openai"

    def test_get_model_config_not_found(self, temp_db):
        client = ManagementDBClient(db_path=temp_db)
        result = client.get_model_config(999)
        assert result is None

    def test_get_active_embedding_config(self, temp_db):
        client = ManagementDBClient(db_path=temp_db)
        result = client.get_active_embedding_config()
        assert result is not None
        assert result["base_url"] == "https://test.api/v1"
        assert result["model_name"] == "text-embedding-3-small"
        assert result["dimension"] == 1536

    def test_get_active_embedding_config_not_found(self, temp_db):
        conn = sqlite3.connect(temp_db)
        conn.execute("DELETE FROM embedding_configs")
        conn.commit()
        conn.close()

        client = ManagementDBClient(db_path=temp_db)
        result = client.get_active_embedding_config()
        assert result is None

    def test_parse_knows_ids_invalid_json(self, temp_db):
        client = ManagementDBClient(db_path=temp_db)
        result = client._parse_knows_ids("invalid json")
        assert result == []

    def test_parse_knows_ids_none(self, temp_db):
        client = ManagementDBClient(db_path=temp_db)
        result = client._parse_knows_ids(None)
        assert result == []

    def test_error_handling(self):
        client = ManagementDBClient(db_path="/nonexistent/path/db.sqlite")
        result = client.get_system_config("TEST_KEY")
        assert result == ""

    def test_get_agent_configs_error(self):
        client = ManagementDBClient(db_path="/nonexistent/path/db.sqlite")
        result = client.get_agent_configs()
        assert result == []

    def test_get_db_client_singleton(self):
        client1 = get_db_client()
        client2 = get_db_client()
        assert client1 is client2
