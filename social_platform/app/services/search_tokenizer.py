# 平台搜索分词工具
# 基于 jieba 搜索引擎模式预分词，交给 Tantivy raw tokenizer 按 token 检索。
import re
from typing import List

import jieba


def tokenize_text(text: str) -> List[str]:
    """
    对正文、标题等自然语言文本做搜索分词。
    """
    value = (text or "").strip()
    if not value:
        return []
    return [token.strip().lower() for token in jieba.cut_for_search(value) if token.strip()]


def tokenize_username(username: str) -> List[str]:
    """
    对用户名做分词，并补充前缀 token，提升短查询的可用性。
    """
    value = (username or "").strip().lower()
    if not value:
        return []

    tokens = set(tokenize_text(value))
    compact = re.sub(r"\s+", "", value)
    if compact:
        tokens.add(compact)
        for index in range(1, len(compact) + 1):
            tokens.add(compact[:index])

    return list(tokens)


def tokens_to_tantivy_text(tokens: List[str]) -> str:
    return " ".join(tokens)
