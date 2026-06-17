from unittest.mock import MagicMock, patch

from agents.agents_scheduler.langgraph.config import SessionConfig


def _build_db_client(model: dict[str, object]) -> MagicMock:
    """
    构造用于 SessionConfig 单测的 management DB client。

    Args:
        model: 模拟的模型配置记录。

    Returns:
        MagicMock: 具备模型配置与系统配置读取方法的 mock client。
    """
    db = MagicMock()
    db.get_system_config.return_value = ""
    db.get_active_model_configs.return_value = [model]
    db.get_model_config.return_value = model
    return db


class TestSessionConfigFromDb:
    def test_from_db_normalizes_openai_provider(self):
        """测试 OpenAI provider 大小写和空白不影响配置解析。"""
        model = {
            "id": 7,
            "provider": " OpenAI ",
            "model_name": " gpt-4o ",
            "api_key": " sk-test ",
            "base_url": " https://example.test/v1 ",
            "temperature": 0.8,
            "is_active": 1,
        }

        with patch(
            "agents.agents_scheduler.langgraph.config.get_db_client",
            return_value=_build_db_client(model),
        ):
            config = SessionConfig.from_db(model_config_id=7)

        assert config.model_config_id == 7
        assert config.llm_provider == "openai"
        assert config.openai_api_key == "sk-test"
        assert config.openai_model_name == "gpt-4o"
        assert config.openai_base_url == "https://example.test/v1"

    def test_from_db_uses_first_active_model_when_unassigned(self):
        """测试未传入角色绑定模型时回退到第一个启用模型。"""
        model = {
            "id": 3,
            "provider": "openai",
            "model_name": "gpt-4o-mini",
            "api_key": "sk-active",
            "base_url": "",
            "temperature": 1.0,
            "is_active": 1,
        }

        db = _build_db_client(model)
        with patch("agents.agents_scheduler.langgraph.config.get_db_client", return_value=db):
            config = SessionConfig.from_db()

        assert config.model_config_id == 3
        assert config.openai_model_name == "gpt-4o-mini"
        db.get_active_model_configs.assert_called_once()

    def test_from_db_treats_unknown_provider_as_openai_compatible(self):
        """测试非 Anthropic provider 按 OpenAI-compatible 模型传参。"""
        model = {
            "id": 9,
            "provider": "deepseek",
            "model_name": "deepseek-chat",
            "api_key": "deepseek-key",
            "base_url": "https://api.deepseek.com/v1",
            "temperature": 1.0,
            "is_active": 1,
        }

        with patch(
            "agents.agents_scheduler.langgraph.config.get_db_client",
            return_value=_build_db_client(model),
        ):
            config = SessionConfig.from_db(model_config_id=9)

        assert config.llm_provider == "deepseek"
        assert config.openai_api_key == "deepseek-key"
        assert config.openai_model_name == "deepseek-chat"
        assert config.openai_base_url == "https://api.deepseek.com/v1"
