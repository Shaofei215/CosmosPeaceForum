# 中文分词工具
# 基于 jieba 搜索引擎模式的分词器，用于 Tantivy BM25 索引

import jieba
from typing import List


def tokenize_chinese(text: str) -> List[str]:
    """
    使用 jieba 搜索引擎模式对中文文本进行分词

    搜索引擎模式会在精确模式基础上对长词再次切分，提高召回率。

    Args:
        text: 待分词的中文文本

    Returns:
        List[str]: 分词结果列表
    """
    return list(jieba.cut_for_search(text))


def tokenize_query(query: str) -> List[str]:
    """
    对查询文本进行分词，用于搜索

    Args:
        query: 查询文本

    Returns:
        List[str]: 分词结果列表
    """
    return tokenize_chinese(query)
