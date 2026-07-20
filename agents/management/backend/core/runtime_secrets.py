"""Agents 运行期密钥的安全生成与持久化工具。

该模块只管理必须跨进程重启保持稳定、但允许由示例默认值自动替换的密钥。
初始管理员密码等一次性凭据不写入该密钥文件，由配置层单独生成并仅在创建账号时输出。
"""

from __future__ import annotations

import json
import os
import secrets
import tempfile
from collections.abc import Mapping, Set
from pathlib import Path


def _load_secret_file(secret_file: Path) -> dict[str, str]:
    """读取并校验运行期密钥文件。

    Args:
        secret_file: JSON 格式的运行期密钥文件路径。

    Returns:
        已保存的环境变量名到密钥值的映射；文件不存在时返回空映射。

    Raises:
        RuntimeError: 文件无法读取、JSON 格式错误或包含非字符串密钥值时抛出。
    """

    if not secret_file.exists():
        return {}
    try:
        raw_values = json.loads(secret_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"无法读取运行期密钥文件: {secret_file}") from exc
    if not isinstance(raw_values, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in raw_values.items()
    ):
        raise RuntimeError(f"运行期密钥文件格式无效: {secret_file}")
    return raw_values


def _write_secret_file(secret_file: Path, values: Mapping[str, str]) -> None:
    """以仅属主可读写的权限原子写入运行期密钥。

    Args:
        secret_file: 目标 JSON 文件路径。
        values: 待持久化的环境变量名到密钥值映射。

    Raises:
        OSError: 目录或文件创建、刷盘、替换失败时抛出。
    """

    secret_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=secret_file.parent,
            prefix=f".{secret_file.name}.",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            os.chmod(temporary_path, 0o600)
            json.dump(dict(values), temporary_file, ensure_ascii=False, indent=2, sort_keys=True)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, secret_file)
        os.chmod(secret_file, 0o600)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def resolve_persistent_secrets(
    configured_values: Mapping[str, str],
    placeholder_values: Mapping[str, Set[str]],
    secret_file: Path,
    *,
    token_bytes: int | Mapping[str, int] = 48,
) -> tuple[dict[str, str], set[str]]:
    """解析显式配置，并为默认占位值生成可跨重启复用的高熵密钥。

    Args:
        configured_values: 当前配置中的环境变量名及其值。
        placeholder_values: 每项配置应视为空缺的示例默认值集合；空白值也视为空缺。
        secret_file: 自动生成值的运行期持久化文件。
        token_bytes: 每个随机值统一使用的随机字节数，或按配置名指定的字节数映射；
            默认 48 字节（384 bit）。

    Returns:
        二元组：最终配置值映射，以及本次采用自动托管值的配置名集合。

    Raises:
        ValueError: 任一 ``token_bytes`` 不是正数时抛出。
        RuntimeError: 已有密钥文件损坏或无法读取时抛出。
        OSError: 新密钥无法安全持久化时抛出。
    """

    if isinstance(token_bytes, int):
        token_bytes_by_key = {key: token_bytes for key in configured_values}
    else:
        token_bytes_by_key = {key: token_bytes.get(key, 48) for key in configured_values}
    if any(byte_count <= 0 for byte_count in token_bytes_by_key.values()):
        raise ValueError("token_bytes 必须为正数")

    automatic_keys = {
        key
        for key, value in configured_values.items()
        if not value.strip() or value.strip() in placeholder_values.get(key, set())
    }
    if not automatic_keys:
        return dict(configured_values), set()

    persisted_values = _load_secret_file(secret_file)
    final_values = dict(configured_values)
    file_changed = False
    for key in automatic_keys:
        persisted_value = persisted_values.get(key, "").strip()
        if not persisted_value:
            persisted_value = secrets.token_urlsafe(token_bytes_by_key[key])
            persisted_values[key] = persisted_value
            file_changed = True
        final_values[key] = persisted_value

    if file_changed:
        _write_secret_file(secret_file, persisted_values)
    else:
        # 修复手工复制或旧版本产生的过宽权限，不改变文件内容。
        os.chmod(secret_file, 0o600)
    return final_values, automatic_keys
