import pytest
from unittest.mock import patch, MagicMock
from unittest.mock import PropertyMock

from agents.agents_scheduler.memory.config import MemoryConfig


class TestMemoryConfig:
    def test_default_values(self):
        config = MemoryConfig()
        assert config.memory_enabled is True
        assert config.recall_limit == 5
        assert config.recall_vector_results == 20
        assert config.recall_bm25_results == 20
        assert config.recall_max_candidates == 200
        assert config.rrf_rank_constant == 60
        assert config.threshold == 0.1
        assert config.importance_weight == 0.3
        assert config.boost_factor == 0.1
        assert config.boost_cooldown_seconds == 86400
        assert config.decay_rate == 0.01
        assert config.decay_interval_seconds == 3600

    def test_validation_valid(self):
        config = MemoryConfig()
        assert config.memory_enabled is True

    def test_validation_recall_limit(self):
        with pytest.raises(ValueError, match="recall_limit"):
            MemoryConfig(recall_limit=0)

    def test_validation_recall_vector_results(self):
        with pytest.raises(ValueError, match="recall_vector_results"):
            MemoryConfig(recall_vector_results=0)

    def test_validation_recall_bm25_results(self):
        with pytest.raises(ValueError, match="recall_bm25_results"):
            MemoryConfig(recall_bm25_results=0)

    def test_validation_recall_max_candidates(self):
        with pytest.raises(ValueError, match="recall_max_candidates"):
            MemoryConfig(recall_max_candidates=0)

    def test_validation_rrf_rank_constant(self):
        with pytest.raises(ValueError, match="rrf_rank_constant"):
            MemoryConfig(rrf_rank_constant=0)

    def test_validation_threshold(self):
        with pytest.raises(ValueError, match="threshold"):
            MemoryConfig(threshold=-0.1)
        with pytest.raises(ValueError, match="threshold"):
            MemoryConfig(threshold=1.1)

    def test_validation_boost_factor(self):
        with pytest.raises(ValueError, match="boost_factor"):
            MemoryConfig(boost_factor=-0.1)
        with pytest.raises(ValueError, match="boost_factor"):
            MemoryConfig(boost_factor=1.1)

    def test_validation_importance_weight(self):
        with pytest.raises(ValueError, match="importance_weight"):
            MemoryConfig(importance_weight=-0.1)
        with pytest.raises(ValueError, match="importance_weight"):
            MemoryConfig(importance_weight=1.1)

    def test_validation_boost_cooldown_seconds(self):
        with pytest.raises(ValueError, match="boost_cooldown_seconds"):
            MemoryConfig(boost_cooldown_seconds=-1)

    def test_validation_decay_rate(self):
        with pytest.raises(ValueError, match="decay_rate"):
            MemoryConfig(decay_rate=0)

    def test_validation_decay_interval_seconds(self):
        with pytest.raises(ValueError, match="decay_interval_seconds"):
            MemoryConfig(decay_interval_seconds=0)

    def test_validation_embedding_dimension(self):
        with pytest.raises(ValueError, match="embedding_dimension"):
            MemoryConfig(embedding_dimension=0)

    def test_get_memory_db_path(self):
        config = MemoryConfig()
        path = config.get_memory_db_path()
        assert path.endswith("memories.db")

    def test_get_chroma_db_path(self):
        config = MemoryConfig()
        path = config.get_chroma_db_path()
        assert path.endswith("chroma_db")

    def test_get_tantivy_index_path(self):
        config = MemoryConfig()
        path = config.get_tantivy_index_path()
        assert path.endswith("tantivy_index")

    def test_from_db_defaults(self):
        with patch("agents.agents_scheduler.memory.config.get_db_client") as mock_db:
            mock_client = MagicMock()
            mock_client.get_system_config.return_value = ""
            mock_client.get_active_embedding_config.return_value = None
            mock_db.return_value = mock_client
            
            config = MemoryConfig.from_db()
            assert isinstance(config, MemoryConfig)
            assert config.memory_enabled is True
            assert config.recall_limit == 5
            assert config.decay_interval_seconds == 3600
            assert config.embedding_dimension == 1536

    def test_from_db_with_embedding_config(self):
        with patch("agents.agents_scheduler.memory.config.get_db_client") as mock_db:
            mock_client = MagicMock()
            mock_client.get_system_config.return_value = ""
            mock_client.get_active_embedding_config.return_value = {
                "base_url": "https://test.api/v1",
                "api_key": "test_key",
                "model_name": "text-embedding-3-large",
                "dimension": 3072,
                "is_active": 1,
            }
            mock_db.return_value = mock_client
            
            config = MemoryConfig.from_db()
            assert config.embedding_base_url == "https://test.api/v1"
            assert config.embedding_api_key == "test_key"
            assert config.embedding_model_name == "text-embedding-3-large"
            assert config.embedding_dimension == 3072
