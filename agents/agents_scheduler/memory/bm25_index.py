# Tantivy BM25 检索层
# 提供基于关键词匹配的记忆检索功能
# 使用 jieba 搜索引擎模式进行中文分词

import tantivy
from typing import List, Dict, Optional
from pathlib import Path

from agents.agents_scheduler.memory.config import MemoryConfig
from agents.agents_scheduler.memory.chinese_tokenizer import tokenize_chinese, tokenize_query


class BM25Index:
    """
    Tantivy BM25 索引封装类

    提供基于关键词匹配的记忆检索功能。
    使用 BM25 算法计算文档相关性。

    中文分词使用 jieba 的搜索引擎模式，在索引构建和搜索时自动分词。

    所有操作都通过 owner_id 实现所有权隔离。
    """

    def __init__(self, config: MemoryConfig):
        """
        初始化 Tantivy 索引

        Args:
            config: 记忆系统配置
        """
        self.config = config
        index_path = config.get_tantivy_index_path()

        # 定义 Schema
        # content 字段使用 'raw' 分词器，因为我们已经通过 jieba 预分词
        # tantivy 的 SimpleAnalyzer 会对 'raw' 字段按空格分割 token
        schema_builder = tantivy.SchemaBuilder()
        schema_builder.add_text_field("id", stored=True, tokenizer_name="raw")
        schema_builder.add_text_field("content", stored=True, tokenizer_name="raw")
        schema_builder.add_unsigned_field("owner_id", stored=True)
        schema = schema_builder.build()

        # 创建或加载索引
        if Path(index_path).exists():
            self.index = tantivy.Index(schema=schema, path=index_path)
        else:
            Path(index_path).mkdir(parents=True, exist_ok=True)
            self.index = tantivy.Index(schema=schema, path=index_path)

        self.writer = self.index.writer()
        self.writer.commit()

    def _ensure_writer(self):
        """确保 writer 可用，如果已被消耗则重新创建"""
        try:
            self.writer.commit()
        except Exception:
            self.writer = self.index.writer()

    def _flush_writer(self):
        """提交并等待合并线程完成，然后重建 writer"""
        self.writer.commit()
        try:
            self.writer.wait_merging_threads()
        except Exception:
            pass
        self.writer = self.index.writer()

    def add_doc(
        self,
        memory_id: str,
        content: str,
        owner_id: int
    ) -> None:
        """
        添加文档到索引

        Args:
            memory_id: 记忆 ID
            content: 记忆内容
            owner_id: 用户 ID
        """
        self._ensure_writer()
        tokenized_content = tokenize_chinese(content)
        self.writer.add_document(tantivy.Document(
            id=memory_id,
            content=tokenized_content,
            owner_id=owner_id
        ))
        self._flush_writer()

    def search(
        self,
        query: str,
        owner_id: int,
        limit: int = 5
    ) -> List[Dict]:
        """
        BM25 关键词检索

        Args:
            query: 查询文本
            owner_id: 用户 ID（用于所有权过滤）
            limit: 返回结果数量

        Returns:
            List[Dict]: 检索结果列表，每个结果包含 id, score, content
        """
        self._ensure_writer()
        self._flush_writer()
        self.index.reload()
        searcher = self.index.searcher()

        # 使用 jieba 对查询分词，然后用空格连接供 tantivy 解析
        tokenized_tokens = tokenize_query(query)
        tokenized_query = " ".join(tokenized_tokens)

        # 使用 parse_query_lenient 构建查询
        try:
            parsed_query, errors = self.index.parse_query_lenient(tokenized_query, ["content"])
        except Exception:
            # 如果查询解析失败，返回空结果
            return []

        # 执行搜索
        # search 返回的 hits 是 (score, DocAddress) 元组列表
        results = []
        top_docs = searcher.search(parsed_query, limit=limit * 3)

        for hit in top_docs.hits:
            # hit 是 (score, DocAddress) 元组
            score, doc_address = hit
            doc = searcher.doc(doc_address)
            doc_owner_id = doc.get_first("owner_id")

            # 所有权过滤
            if doc_owner_id == owner_id:
                results.append({
                    "id": doc.get_first("id") or "",
                    "score": score,
                    "content": doc.get_first("content") or "",
                })

            if len(results) >= limit:
                break

        return results

    def delete_doc(self, memory_id: str) -> None:
        """
        删除文档

        Args:
            memory_id: 要删除的记忆 ID
        """
        self._ensure_writer()
        self.writer.delete_documents("id", memory_id)
        self._flush_writer()

    def get_doc_count(self, owner_id: Optional[int] = None) -> int:
        """
        获取文档数量

        Args:
            owner_id: 用户 ID（可选，如果提供则只统计该用户的文档）

        Returns:
            int: 文档数量
        """
        self._ensure_writer()
        self._flush_writer()
        self.index.reload()
        searcher = self.index.searcher()

        if owner_id is not None:
            # 遍历所有文档并过滤
            count = 0
            all_query, _ = self.index.parse_query_lenient("*", ["content"])
            top_docs = searcher.search(all_query, limit=searcher.num_docs)
            for hit in top_docs.hits:
                score, doc_address = hit
                doc = searcher.doc(doc_address)
                doc_owner_id = doc.get_first("owner_id")
                if doc_owner_id == owner_id:
                    count += 1
            return count

        return searcher.num_docs
