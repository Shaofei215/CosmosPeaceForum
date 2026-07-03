"""外部 Agent 公共 Skill 运行时渲染与下载测试。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from social_platform.app.api.routers import external_agent_skill as skill_router
from social_platform.app.services.external_agent_skill import (
    SKILL_VERSION,
    SOURCE_FILES,
    SkillPackage,
    build_skill_package,
    create_skill_build_config,
    normalize_skill_name,
)


def _build_package(agent_api_base: str) -> SkillPackage:
    """构建测试使用的自定义品牌 Skill 包。

    Args:
        agent_api_base: 当前测试场景的外部工具网关根地址。

    Returns:
        SkillPackage: 已完成渲染的内存包。
    """

    config = create_skill_build_config(
        platform_display_name="星海社区",
        platform_english_name="Stellar Community",
        public_frontend_url="https://community.example",
        api_v1_prefix="/api/v1",
        external_agent_api_base_url=agent_api_base,
    )
    return build_skill_package(config)


def test_skill_name_uses_normalized_platform_english_name() -> None:
    """平台外文名必须生成满足 Skill 规范的 ASCII 机器标识。"""

    assert normalize_skill_name("Cosmos Peace Forum") == "cosmos-peace-forum"
    assert normalize_skill_name("Café Agents") == "cafe-agents"

    with pytest.raises(ValueError, match="ASCII letters or digits"):
        normalize_skill_name("宇宙和平论坛")
    with pytest.raises(ValueError, match="64 characters"):
        normalize_skill_name("a" * 65)


@pytest.mark.parametrize(
    "agent_api_base",
    [
        "http://localhost:8001/external/v1",
        "https://community.example/agent-api/v1",
    ],
)
def test_skill_package_renders_deployment_specific_urls(agent_api_base: str) -> None:
    """个人与生产部署的真实工具网关地址必须分别写入整个 Skill 包。"""

    package = _build_package(agent_api_base)

    with ZipFile(BytesIO(package.archive)) as archive:
        names = tuple(item.filename for item in archive.infolist() if not item.is_dir())
        rendered_files = {
            name: archive.read(name).decode("utf-8")
            for name in names
        }

    assert names == SOURCE_FILES
    assert package.manifest["name"] == "stellar-community"
    assert package.manifest["platform_display_name"] == "星海社区"
    assert package.manifest["platform_english_name"] == "Stellar Community"
    assert package.manifest["platform_api_base"] == "https://community.example/api/v1"
    assert package.manifest["agent_api_base"] == agent_api_base
    assert package.manifest["version"] == SKILL_VERSION
    assert package.download_filename == f"stellar-community-skill-v{SKILL_VERSION}.zip"

    assert rendered_files["SKILL.md"].startswith("---\nname: stellar-community\n")
    assert 'platform_api_base: "https://community.example/api/v1"' in rendered_files["SKILL.md"]
    assert f'agent_api_base: "{agent_api_base}"' in rendered_files["SKILL.md"]
    assert 'platform_api_base: "https://community.example/api/v1"' in rendered_files[
        "references/API.md"
    ]
    assert f'agent_api_base: "{agent_api_base}"' in rendered_files["references/API.md"]
    assert all("星海社区" in text for text in rendered_files.values())
    assert all("CosmosPeaceForum" not in text for text in rendered_files.values())
    assert all("{{SKILL_NAME}}" not in text for text in rendered_files.values())
    assert all("{{PLATFORM_NAME}}" not in text for text in rendered_files.values())
    assert "{{ACCOUNT_EMAIL}}" in rendered_files["SKILL.md"]
    assert "{{ACCOUNT_PASSWORD}}" in rendered_files["SKILL.md"]
    assert "agent_context" in rendered_files["references/API.md"]
    for tool_name in (
        "vote_post_poll",
        "delete_content",
        "report_content",
        "repost",
        "view_full_hot_topics",
        "update_profile",
        "logout",
    ):
        assert tool_name in rendered_files["references/TOOLS.md"]
    assert "/profile/avatar" in rendered_files["references/API.md"]
    assert "最大 5MB" in rendered_files["references/API.md"]

    license_directory = Path(__file__).resolve().parents[1] / "license"
    agreement_sources = {
        "references/TERMS_OF_SERVICE.md": "terms-of-service.md",
        "references/PRIVACY_POLICY.md": "privacy-policy.md",
        "references/COMMUNITY_GUIDELINES.md": "community-guidelines.md",
    }
    for agreement_path, source_name in agreement_sources.items():
        assert agreement_path in package.manifest["files"]
        assert "星海社区" in rendered_files[agreement_path]
        expected = (license_directory / source_name).read_text(encoding="utf-8").replace(
            "{{PLATFORM_NAME}}",
            "星海社区",
        )
        assert rendered_files[agreement_path] == expected


@pytest.mark.parametrize(
    "invalid_url,error",
    [
        ("localhost:8001/external/v1", "absolute HTTP"),
        ("https://user:secret@example.com/external/v1", "credentials"),
        ("https://example.com/external/v1?mode=agent", "query or fragment"),
    ],
)
def test_skill_config_rejects_unsafe_public_urls(invalid_url: str, error: str) -> None:
    """写入 Skill 的公开 URL 不得为相对地址或携带敏感及不稳定部分。"""

    with pytest.raises(ValueError, match=error):
        create_skill_build_config(
            platform_display_name="星海社区",
            platform_english_name="Stellar Community",
            public_frontend_url="https://community.example",
            api_v1_prefix="/api/v1",
            external_agent_api_base_url=invalid_url,
        )


def test_download_routes_return_cached_runtime_package(monkeypatch: pytest.MonkeyPatch) -> None:
    """下载端点必须返回同一份部署级缓存以及平台化下载文件名。"""

    settings = SimpleNamespace(
        PLATFORM_DISPLAY_NAME="星海社区",
        PLATFORM_ENGLISH_NAME="Stellar Community",
        SOCIAL_PLATFORM_FRONTEND_URL="http://localhost:8000",
        API_V1_PREFIX="/api/v1",
        EXTERNAL_AGENT_API_BASE_URL="http://localhost:8001/external/v1",
    )
    monkeypatch.setattr(skill_router, "get_settings", lambda: settings)
    skill_router.get_runtime_skill_package.cache_clear()

    manifest_response = skill_router.download_skill_manifest()
    latest_response = skill_router.download_latest_skill()
    version_response = skill_router.download_versioned_skill()

    assert manifest_response.status_code == 200
    assert b'"agent_api_base":"http://localhost:8001/external/v1"' in manifest_response.body
    assert latest_response.status_code == 200
    assert latest_response.media_type == "application/zip"
    assert latest_response.headers["content-disposition"] == (
        f'attachment; filename="stellar-community-skill-v{SKILL_VERSION}.zip"'
    )
    assert latest_response.body == version_response.body
    assert skill_router.get_runtime_skill_package.cache_info().misses == 1

    skill_router.get_runtime_skill_package.cache_clear()
