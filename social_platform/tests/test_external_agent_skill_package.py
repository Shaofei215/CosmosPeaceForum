"""外部 Agent 公共 Skill 下载包测试。"""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from social_platform.scripts import build_external_agent_skill


def _skill_dir() -> Path:
    """返回测试使用的公共 Skill 静态下载目录。

    Returns:
        Path: ``social_platform`` 侧 Skill 下载目录。
    """

    return build_external_agent_skill._skill_dir()


def test_skill_manifest_matches_latest_zip_contents() -> None:
    """manifest 文件列表必须与 latest.zip 内部文件完全一致。"""

    skill_dir = _skill_dir()
    config = build_external_agent_skill._skill_build_config()
    manifest = json.loads((skill_dir / "manifest.json").read_text(encoding="utf-8"))

    with ZipFile(skill_dir / "latest.zip") as archive:
        names = sorted(item.filename for item in archive.infolist() if not item.is_dir())
        total_size = sum(item.file_size for item in archive.infolist())

    assert total_size > 0
    assert manifest["platform_display_name"] == config.platform_display_name
    assert manifest["platform_api_base"] == config.platform_api_base
    assert manifest["agent_api_base"] == config.agent_api_base
    assert sorted(manifest["files"]) == names
    assert set(names) == {
        "SKILL.md",
        "RULES.md",
        "references/API.md",
        "references/TOOLS.md",
    }


def test_skill_zip_uses_social_platform_source_files() -> None:
    """zip 内文件内容必须来自 social_platform 静态目录源文件和构建配置。"""

    skill_dir = _skill_dir()
    config = build_external_agent_skill._skill_build_config()

    with ZipFile(skill_dir / "latest.zip") as archive:
        for relative_path in build_external_agent_skill.SOURCE_FILES:
            archived = archive.read(relative_path).decode("utf-8")
            source = build_external_agent_skill._read_source_file(skill_dir, relative_path, config)

            assert archived == source


def test_skill_zip_uses_real_platform_config_without_credential_origin() -> None:
    """Skill 配置必须使用构建配置，且不再暴露 allowed_credential_origin。"""

    skill_dir = _skill_dir()
    config = build_external_agent_skill._skill_build_config()

    with ZipFile(skill_dir / "latest.zip") as archive:
        skill_md = archive.read("SKILL.md").decode("utf-8")

    rendered_files = skill_md
    assert config.platform_display_name in rendered_files
    assert f'platform_api_base: "{config.platform_api_base}"' in rendered_files
    assert f'agent_api_base: "{config.agent_api_base}"' in rendered_files
    assert "https://example.com" not in rendered_files
    assert "allowed_credential_origin" not in rendered_files
