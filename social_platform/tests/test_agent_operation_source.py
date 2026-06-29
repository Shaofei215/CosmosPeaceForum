"""可信 Agent 操作来源依赖测试。"""

from social_platform.app.api import deps


def test_agent_operation_source_requires_matching_source_and_token(monkeypatch) -> None:
    """只有固定来源值和常量时间校验通过的 Secret 才能标记 Agent 来源。"""

    monkeypatch.setattr(deps.get_settings(), "AGENT_SERVICE_TOKEN", "shared-secret")

    assert deps.get_agent_operation_source("agent", "shared-secret") is True
    assert deps.get_agent_operation_source("agent", "wrong-secret") is False
    assert deps.get_agent_operation_source("browser", "shared-secret") is False
    assert deps.get_agent_operation_source(None, None) is False


def test_agent_operation_source_is_disabled_without_deployment_secret(monkeypatch) -> None:
    """平台未配置部署 Secret 时任何 Header 都不能伪造 Agent 来源。"""

    monkeypatch.setattr(deps.get_settings(), "AGENT_SERVICE_TOKEN", "")

    assert deps.get_agent_operation_source("agent", "anything") is False
