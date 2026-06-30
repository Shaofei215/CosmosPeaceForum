"""构建 CosmosPeaceForum 外部 Agent 公共 Skill 下载包。

该脚本以 ``social_platform/app/static_downloads/cosmos-peace-forum-skill`` 为唯一
包体来源，生成同目录下的 ``latest.zip``、版本 zip 和 ``manifest.json``。公开
前端下载请求由 social_platform 服务处理，因此包体不再从 agents 目录复制。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PACKAGE_NAME = "cosmos-peace-forum"
VERSION = "1.0.0"
AGENT_API_PREFIX = "/agent-api/v1"
SOURCE_FILES = [
    "SKILL.md",
    "RULES.md",
    "references/API.md",
    "references/TOOLS.md",
]
TEMPLATE_SOURCE_FILES = {"SKILL.md"}


@dataclass(frozen=True)
class SkillBuildConfig:
    """公共 Skill 构建时注入的非敏感平台配置。

    Attributes:
        platform_display_name: 平台对外展示名，来自 ``social_platform/.env``。
        platform_api_base: 公开平台 API 根地址。
        agent_api_base: 外部 Agent 工具网关根地址。
    """

    platform_display_name: str
    platform_api_base: str
    agent_api_base: str


def _repo_root() -> Path:
    """返回仓库根目录。

    Returns:
        Path: 当前脚本所在 social_platform 目录的父目录。
    """

    return Path(__file__).resolve().parents[2]


def _skill_dir() -> Path:
    """返回公共 Skill 包体目录。

    Returns:
        Path: social_platform 静态下载目录中的 Skill 包目录。
    """

    return _repo_root() / "social_platform" / "app" / "static_downloads" / "cosmos-peace-forum-skill"


def _env_file() -> Path:
    """返回构建脚本读取的 social_platform 环境文件路径。

    Returns:
        Path: ``social_platform/.env`` 的绝对路径。
    """

    return _repo_root() / "social_platform" / ".env"


def _parse_env_line(line: str) -> tuple[str, str] | None:
    """解析单行 ``KEY=VALUE`` 环境配置。

    Args:
        line: 来自 ``.env`` 文件的一行文本。

    Returns:
        tuple[str, str] | None: 解析成功时返回键值对，空行、注释或非法行返回 ``None``。
    """

    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def _load_env_values() -> dict[str, str]:
    """读取构建所需的 ``social_platform/.env`` 配置。

    构建脚本只使用项目的公开平台配置文件。缺少该文件时直接失败，避免静默产出
    带错误地址的 Skill 包。

    Returns:
        dict[str, str]: ``.env`` 中解析出的配置映射。

    Raises:
        FileNotFoundError: ``social_platform/.env`` 不存在。
    """

    env_path = _env_file()
    if not env_path.exists():
        raise FileNotFoundError(f"social_platform env file not found: {env_path}")

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        item = _parse_env_line(line)
        if item:
            key, value = item
            values[key] = value
    return values


def _require_env_value(values: dict[str, str], key: str) -> str:
    """读取必需的非空配置值。

    Args:
        values: 从 ``social_platform/.env`` 解析出的配置映射。
        key: 必需配置项名称。

    Returns:
        str: 去除首尾空白后的配置值。

    Raises:
        ValueError: 配置缺失或为空。
    """

    value = values.get(key, "").strip()
    if not value:
        raise ValueError(f"social_platform/.env missing required value: {key}")
    return value


def _strip_trailing_slash(value: str) -> str:
    """移除 URL 末尾斜杠。

    Args:
        value: 原始 URL 或路径。

    Returns:
        str: 去除首尾空白和末尾斜杠后的值。
    """

    return value.strip().rstrip("/")


def _join_url(base: str, suffix: str) -> str:
    """拼接公开 origin 和固定 API 前缀。

    Args:
        base: 公开平台 origin。
        suffix: API 路径前缀。

    Returns:
        str: 拼接后的完整根地址。
    """

    return f"{_strip_trailing_slash(base)}/{suffix.strip('/')}"


def _skill_build_config() -> SkillBuildConfig:
    """生成当前构建使用的公共 Skill 平台配置。

    Returns:
        SkillBuildConfig: 已规范化的展示名和 API 根地址。
    """

    values = _load_env_values()
    platform_display_name = _require_env_value(values, "PLATFORM_DISPLAY_NAME")
    public_frontend_url = _require_env_value(values, "SOCIAL_PALTFORM_FRONTEND_URL")
    api_prefix = _require_env_value(values, "API_V1_PREFIX")

    return SkillBuildConfig(
        platform_display_name=platform_display_name,
        platform_api_base=_join_url(public_frontend_url, api_prefix),
        agent_api_base=_join_url(public_frontend_url, AGENT_API_PREFIX),
    )


def _render_template(text: str, config: SkillBuildConfig) -> str:
    """渲染 Skill 源文件中的非敏感平台占位符。

    Args:
        text: 模板源文件内容。
        config: 当前构建的平台配置。

    Returns:
        str: 注入展示名和 URL 后的文件内容。
    """

    replacements = {
        "{{PLATFORM_DISPLAY_NAME}}": config.platform_display_name,
        "{{PLATFORM_API_BASE}}": config.platform_api_base,
        "{{AGENT_API_BASE}}": config.agent_api_base,
    }
    rendered = text
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


def _read_source_file(skill_dir: Path, relative_path: str, config: SkillBuildConfig) -> str:
    """读取并按需渲染 Skill 源文件。

    Args:
        skill_dir: Skill 包体源目录。
        relative_path: 相对 ``skill_dir`` 的源文件路径。
        config: 当前构建的平台配置。

    Returns:
        str: zip 中应写入的最终文本内容。

    Raises:
        FileNotFoundError: 源文件不存在。
    """

    source = skill_dir / relative_path
    if not source.is_file():
        raise FileNotFoundError(f"Skill source file not found: {source}")
    text = source.read_text(encoding="utf-8")
    if relative_path in TEMPLATE_SOURCE_FILES:
        return _render_template(text, config)
    return text


def _manifest(files: list[str], config: SkillBuildConfig) -> dict[str, object]:
    """生成下载清单内容。

    Args:
        files: zip 内部文件路径列表。
        config: 当前构建的平台配置。

    Returns:
        dict[str, object]: 可序列化为 ``manifest.json`` 的清单。
    """

    return {
        "name": PACKAGE_NAME,
        "version": VERSION,
        "schema_version": "1",
        "description": f"使用普通 {config.platform_display_name} 账号安全接入外部 Agent。",
        "platform_display_name": config.platform_display_name,
        "platform_api_base": config.platform_api_base,
        "agent_api_base": config.agent_api_base,
        "latest": "/downloads/cosmos-peace-forum-skill/latest.zip",
        "versions": [
            {
                "version": VERSION,
                "url": f"/downloads/cosmos-peace-forum-skill/v{VERSION}.zip",
            }
        ],
        "files": files,
    }


def _write_zip(skill_dir: Path, target: Path, files: list[str], config: SkillBuildConfig) -> None:
    """写入 zip 下载包。

    Args:
        skill_dir: Skill 包体源目录。
        target: 目标 zip 文件路径。
        files: 相对 ``skill_dir`` 的源文件列表。
        config: 当前构建的平台配置。

    Raises:
        FileNotFoundError: 源文件不存在。
    """

    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        for relative_path in files:
            content = _read_source_file(skill_dir, relative_path, config)
            archive.writestr(relative_path, content)


def build_skill_package() -> None:
    """生成 manifest 和所有 zip 下载包。

    Raises:
        FileNotFoundError: 任一源文件缺失时抛出。
    """

    skill_dir = _skill_dir()
    config = _skill_build_config()
    manifest_path = skill_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(_manifest(SOURCE_FILES, config), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_zip(skill_dir, skill_dir / "latest.zip", SOURCE_FILES, config)
    _write_zip(skill_dir, skill_dir / f"v{VERSION}.zip", SOURCE_FILES, config)


if __name__ == "__main__":
    build_skill_package()
