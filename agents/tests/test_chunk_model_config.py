"""
测试分块模型配置服务层
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from agents.management.backend.schemas import (
    ChunkModelConfigCreate,
    ChunkModelConfigUpdate,
)


class TestChunkModelConfigSchemas:
    """测试分块模型配置的 Pydantic schemas"""

    def test_chunk_model_config_create(self):
        schema = ChunkModelConfigCreate(
            name="GPT-4 Chunker",
            provider="openai",
            api_key="sk-test123",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4o",
            temperature=0.7,
            max_token=4096,
            is_active=True,
        )
        assert schema.name == "GPT-4 Chunker"
        assert schema.provider == "openai"
        assert schema.temperature == 0.7

    def test_chunk_model_config_create_defaults(self):
        schema = ChunkModelConfigCreate(
            name="Test",
            provider="openai",
            api_key="sk-test",
            model_name="gpt-4o",
        )
        assert schema.temperature == 1.2
        assert schema.max_token == 4096
        assert schema.is_active is True
        assert schema.base_url == ""

    def test_chunk_model_config_update_partial(self):
        schema = ChunkModelConfigUpdate(
            temperature=0.8,
        )
        update_data = schema.model_dump(exclude_unset=True)
        assert "temperature" in update_data
        assert "name" not in update_data

    def test_chunk_model_config_update_all_fields(self):
        schema = ChunkModelConfigUpdate(
            name="New Name",
            provider="anthropic",
            api_key="new-key",
            base_url="https://api.anthropic.com",
            model_name="claude-3",
            temperature=0.5,
            is_active=False,
            max_token=2048,
        )
        update_data = schema.model_dump(exclude_unset=True)
        assert len(update_data) == 8


class TestChunkModelConfigService:
    """测试分块模型服务层功能"""

    def test_create_chunk_model_config(self):
        from agents.management.backend.services.chunk_model_service import create_chunk_model_config

        mock_db = MagicMock()
        mock_config = MagicMock()
        mock_config.id = 1
        mock_config.name = "GPT-4 Chunker"
        mock_config.provider = "openai"
        mock_config.api_key = "sk-test"
        mock_config.base_url = ""
        mock_config.model_name = "gpt-4o"
        mock_config.temperature = 0.7
        mock_config.is_active = True
        mock_config.max_token = 4096

        mock_db.get.return_value = mock_config
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        create_in = ChunkModelConfigCreate(
            name="GPT-4 Chunker",
            provider="openai",
            api_key="sk-test",
            model_name="gpt-4o",
        )

        with patch(
            "agents.management.backend.services.chunk_model_service.ChunkModelConfig",
            return_value=mock_config,
        ):
            result = create_chunk_model_config(mock_db, create_in)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        assert result == mock_config

    def test_chunk_model_config_to_response(self):
        from agents.management.backend.services.chunk_model_service import chunk_model_config_to_response

        mock_config = MagicMock()
        mock_config.id = 1
        mock_config.name = "Test Chunker"
        mock_config.provider = "openai"
        mock_config.base_url = "https://api.test.com"
        mock_config.model_name = "gpt-4o"
        mock_config.temperature = 0.7
        mock_config.is_active = True
        mock_config.max_token = 4096
        mock_config.created_at = datetime.utcnow()
        mock_config.updated_at = datetime.utcnow()

        response = chunk_model_config_to_response(mock_config)
        assert response["id"] == 1
        assert response["name"] == "Test Chunker"
        assert response["provider"] == "openai"
