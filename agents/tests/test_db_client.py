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
            app_platform_user_id TEXT,
            monthly_logins INTEGER DEFAULT 30
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

    cursor.execute("INSERT INTO system_configs (key, value) VALUES (?, ?)", ("TEST_KEY", "test_value"))
    cursor.execute(
        "INSERT INTO agent_configs (id, username, name, is_active, knows_ids) VALUES (?, ?, ?, ?, ?)",
        (1, "test_user", "Test", 1, '[2, 3]')
    )
    cursor.execute(
        "INSERT INTO model_configs (id, provider, model_name, api_key, is_active, temperature) VALUES (?, ?, ?, ?, ?, ?)",
        (1, "openai", "gpt-4", "test_key", 1, 1.0)
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
        result = client.get_agent_configs()
        assert isinstance(result, list)
        assert len(result) > 0
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
