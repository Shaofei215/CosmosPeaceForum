"""渲染并打包公开外部 Agent Skill。

本模块以应用内的只读模板为输入，把当前部署的品牌与公开 API 地址注入 Skill，
供下载路由生成 manifest 和 zip。它不读取账号凭据，也不写入运行期文件。
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zipfile import ZIP_DEFLATED, ZipFile


SKILL_VERSION = "1.3.0"
SKILL_SCHEMA_VERSION = "1"
DOWNLOAD_BASE_PATH = "/downloads/cosmos-peace-forum-skill"
_SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_TEMPLATE_DIRECTORY = Path(__file__).resolve().parents[1] / "skill_templates" / "external_agent"
_LICENSE_DIRECTORY = Path(__file__).resolve().parents[2] / "license"
_SOURCE_PATHS: dict[str, Path] = {
    "SKILL.md": _TEMPLATE_DIRECTORY / "SKILL.md",
    "RULES.md": _TEMPLATE_DIRECTORY / "RULES.md",
    "references/API.md": _TEMPLATE_DIRECTORY / "references" / "API.md",
    "references/TOOLS.md": _TEMPLATE_DIRECTORY / "references" / "TOOLS.md",
    "references/TERMS_OF_SERVICE.md": _LICENSE_DIRECTORY / "terms-of-service.md",
    "references/PRIVACY_POLICY.md": _LICENSE_DIRECTORY / "privacy-policy.md",
    "references/COMMUNITY_GUIDELINES.md": _LICENSE_DIRECTORY / "community-guidelines.md",
}
SOURCE_FILES = tuple(_SOURCE_PATHS)


@dataclass(frozen=True)
class SkillBuildConfig:
    """公共 Skill 渲染使用的非敏感部署配置。

    Attributes:
        platform_display_name: 平台面向用户的展示名，可使用中文。
        platform_english_name: 平台外文名，用于生成机器标识。
        skill_name: 满足 Skill 规范的 ASCII 机器标识。
        platform_api_base: 外部 Agent 可访问的公开平台 API 根地址。
        agent_api_base: 外部 Agent 可访问的工具网关根地址。
    """

    platform_display_name: str
    platform_english_name: str
    skill_name: str
    platform_api_base: str
    agent_api_base: str


@dataclass(frozen=True)
class SkillPackage:
    """已经渲染完成、可直接返回给下载请求的 Skill 包。

    Attributes:
        manifest: 下载清单及当前部署的公开配置。
        archive: 包含 Skill 文件的 zip 字节串。
        download_filename: HTTP 下载响应使用的安全 ASCII 文件名。
    """

    manifest: dict[str, object]
    archive: bytes
    download_filename: str


def normalize_skill_name(platform_english_name: str) -> str:
    """把平台外文名规范化为合法 Skill 机器标识。

    Args:
        platform_english_name: 部署者配置的平台外文名。

    Returns:
        str: 仅包含小写字母、数字和连字符的机器标识。

    Raises:
        ValueError: 外文名为空、无法生成 ASCII 标识或结果超过 64 字符。
    """

    english_name = platform_english_name.strip()
    if not english_name:
        raise ValueError("PLATFORM_ENGLISH_NAME must not be empty")

    ascii_name = (
        unicodedata.normalize("NFKD", english_name)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    skill_name = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")
    if not skill_name or not _SKILL_NAME_PATTERN.fullmatch(skill_name):
        raise ValueError("PLATFORM_ENGLISH_NAME must contain ASCII letters or digits")
    if len(skill_name) > 64:
        raise ValueError("normalized Skill name must not exceed 64 characters")
    return skill_name


def normalize_public_url(value: str, config_name: str) -> str:
    """校验并规范化写入公共 Skill 的 HTTP(S) 根地址。

    Args:
        value: 待校验的公开 URL。
        config_name: 错误信息中使用的配置项名称。

    Returns:
        str: 去除根路径末尾斜杠后的公开 URL。

    Raises:
        ValueError: URL 缺少 HTTP(S) scheme、主机，或包含凭据、查询和片段。
    """

    normalized = value.strip()
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{config_name} must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{config_name} must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError(f"{config_name} must not contain a query or fragment")

    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def join_public_url(origin: str, path_prefix: str) -> str:
    """把公开平台 origin 与 API 路径前缀拼接为绝对地址。

    Args:
        origin: 浏览器可访问的公开平台 origin。
        path_prefix: 公开平台 API 路径前缀。

    Returns:
        str: 规范化后的公开平台 API 根地址。

    Raises:
        ValueError: origin 或最终地址不是安全的公开 HTTP(S) URL。
    """

    normalized_origin = normalize_public_url(origin, "SOCIAL_PLATFORM_FRONTEND_URL")
    return normalize_public_url(
        f"{normalized_origin}/{path_prefix.strip('/')}",
        "platform_api_base",
    )


def create_skill_build_config(
    *,
    platform_display_name: str,
    platform_english_name: str,
    public_frontend_url: str,
    api_v1_prefix: str,
    external_agent_api_base_url: str,
) -> SkillBuildConfig:
    """根据应用配置创建公共 Skill 渲染配置。

    Args:
        platform_display_name: 平台面向用户的展示名。
        platform_english_name: 用于生成 Skill 机器标识的平台外文名。
        public_frontend_url: 浏览器可访问的公开平台 origin。
        api_v1_prefix: 公开平台 API 路径前缀。
        external_agent_api_base_url: 外部 Agent 可访问的工具网关根地址。

    Returns:
        SkillBuildConfig: 已完成名称和 URL 校验的渲染配置。

    Raises:
        ValueError: 展示名、外文名或任一公开 URL 无效。
    """

    display_name = platform_display_name.strip()
    english_name = platform_english_name.strip()
    if not display_name:
        raise ValueError("PLATFORM_DISPLAY_NAME must not be empty")

    return SkillBuildConfig(
        platform_display_name=display_name,
        platform_english_name=english_name,
        skill_name=normalize_skill_name(english_name),
        platform_api_base=join_public_url(public_frontend_url, api_v1_prefix),
        agent_api_base=normalize_public_url(
            external_agent_api_base_url,
            "EXTERNAL_AGENT_API_BASE_URL",
        ),
    )


def _yaml_double_quoted(value: str) -> str:
    """把文本编码为可安全写入 YAML frontmatter 的双引号字符串。

    Args:
        value: 待编码的用户可见文本。

    Returns:
        str: 与 JSON/YAML 双引号标量兼容的字符串。
    """

    return json.dumps(value, ensure_ascii=False)


def _render_template(text: str, config: SkillBuildConfig) -> str:
    """渲染模板中的部署级非敏感占位符。

    Args:
        text: Skill 模板原文。
        config: 当前部署的渲染配置。

    Returns:
        str: 可写入下载包的最终文本。
    """

    description = (
        f"使用社交平台 {config.platform_display_name} 参与互动。"
    )
    replacements = {
        "{{SKILL_NAME}}": config.skill_name,
        "{{SKILL_DESCRIPTION_YAML}}": _yaml_double_quoted(description),
        "{{PLATFORM_DISPLAY_NAME}}": config.platform_display_name,
        "{{PLATFORM_NAME}}": config.platform_display_name,
        "{{PLATFORM_ENGLISH_NAME}}": config.platform_english_name,
        "{{PLATFORM_API_BASE}}": config.platform_api_base,
        "{{AGENT_API_BASE}}": config.agent_api_base,
    }
    rendered = text
    for placeholder, replacement in replacements.items():
        rendered = rendered.replace(placeholder, replacement)
    return rendered


def _read_rendered_source(relative_path: str, config: SkillBuildConfig) -> str:
    """读取并渲染单个 Skill 模板文件。

    Args:
        relative_path: 下载包内的文件路径。
        config: 当前部署的渲染配置。

    Returns:
        str: 渲染完成的 UTF-8 文本。

    Raises:
        FileNotFoundError: 模板文件不存在。
    """

    source = _SOURCE_PATHS.get(relative_path)
    if source is None:
        raise FileNotFoundError(f"Unknown Skill source: {relative_path}")
    if not source.is_file():
        raise FileNotFoundError(f"Skill template not found: {source}")
    return _render_template(source.read_text(encoding="utf-8"), config)


def _create_manifest(config: SkillBuildConfig) -> dict[str, object]:
    """生成当前部署的 Skill 下载清单。

    Args:
        config: 当前部署的渲染配置。

    Returns:
        dict[str, object]: 可直接序列化为 JSON 的下载清单。
    """

    return {
        "name": config.skill_name,
        "version": SKILL_VERSION,
        "schema_version": SKILL_SCHEMA_VERSION,
        "description": f"让外部 Agent 使用普通 {config.platform_display_name} 账号参与社区互动。",
        "platform_display_name": config.platform_display_name,
        "platform_english_name": config.platform_english_name,
        "platform_api_base": config.platform_api_base,
        "agent_api_base": config.agent_api_base,
        "latest": f"{DOWNLOAD_BASE_PATH}/latest.zip",
        "versions": [
            {
                "version": SKILL_VERSION,
                "url": f"{DOWNLOAD_BASE_PATH}/v{SKILL_VERSION}.zip",
            }
        ],
        "files": list(SOURCE_FILES),
    }


def build_skill_package(config: SkillBuildConfig) -> SkillPackage:
    """在内存中构建当前部署可下载的公共 Skill 包。

    Args:
        config: 当前部署的渲染配置。

    Returns:
        SkillPackage: manifest、zip 字节串和下载文件名。

    Raises:
        FileNotFoundError: 任一模板文件不存在。
    """

    archive_buffer = BytesIO()
    with ZipFile(archive_buffer, "w", compression=ZIP_DEFLATED) as archive:
        for relative_path in SOURCE_FILES:
            archive.writestr(relative_path, _read_rendered_source(relative_path, config))

    return SkillPackage(
        manifest=_create_manifest(config),
        archive=archive_buffer.getvalue(),
        download_filename=f"{config.skill_name}-skill-v{SKILL_VERSION}.zip",
    )
