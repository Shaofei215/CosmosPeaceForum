# Tantivy BM25 检索层
# 提供基于关键词匹配的记忆检索功能

import tantivy
from typing import List, Dict, Optional
from pathlib import Path

from agent_scheduler.memory.config import MemoryConfig


class BM25Index:
    """
    Tantivy BM25 索引封装类

    提供基于关键词匹配的记忆检索功能。
    使用 BM25 算法计算文档相关性。

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
        schema_builder = tantivy.SchemaBuilder()
        schema_builder.add_text_field("id", stored=True)
        schema_builder.add_text_field("content", stored=True)
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
        self.writer.add_document(tantivy.Document(
            id=memory_id,
            content=content,
            owner_id=owner_id
        ))
        self.writer.commit()

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
        self.writer.commit()
        searcher = self.index.searcher()

        # 使用 index.parse_query 构建查询（tantivy 0.24.0 API）
        try:
            parsed_query = self.index.parse_query(query, ["content"])
        except Exception:
            # 如果查询解析失败，返回空结果
            return []

        # 执行搜索
        results = []
        top_docs = searcher.search(parsed_query, limit=limit * 3)

        for doc_address in top_docs.hits:
            doc = searcher.doc(doc_address.doc_id)
            doc_owner_id = doc.get_first("owner_id")

            # 所有权过滤
            if doc_owner_id == owner_id:
                results.append({
                    "id": doc.get_first("id") or "",
                    "score": doc_address.score,
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
        # Tantivy 0.24.0 使用 delete_term 删除
        term = tantivy.Term("id", memory_id)
        self.writer.delete_term(term)
        self.writer.commit()

    def get_doc_count(self, owner_id: Optional[int] = None) -> int:
        """
        获取文档数量

        Args:
            owner_id: 用户 ID（可选，如果提供则只统计该用户的文档）

        Returns:
            int: 文档数量
        """
        self.writer.commit()
        searcher = self.index.searcher()

        if owner_id is not None:
            # 遍历所有文档并过滤
            count = 0
            all_query = self.index.parse_query("*", ["content"])
            top_docs = searcher.search(all_query, limit=searcher.num_docs)
            for doc_address in top_docs.hits:
                doc = searcher.doc(doc_address.doc_id)
                doc_owner_id = doc.get_first("owner_id")
                if doc_owner_id == owner_id:
                    count += 1
            return count

        return searcher.num_docs
