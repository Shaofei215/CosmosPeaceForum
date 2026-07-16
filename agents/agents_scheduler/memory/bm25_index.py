# Tantivy BM25 检索层
# 提供基于关键词匹配的记忆检索功能
# 使用 jieba 搜索引擎模式进行中文分词

import shutil
import threading
from typing import List, Dict, Optional
from pathlib import Path

import tantivy

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

    INDEX_SCHEMA_VERSION = "2"
    VERSION_FILE_NAME = ".schema_version"

    def __init__(self, config: MemoryConfig):
        """
        初始化 Tantivy 索引

        Args:
            config: 记忆系统配置
        """
        self.config = config
        self._lock = threading.RLock()
        self.index_path = Path(config.get_tantivy_index_path())
        version_path = self.index_path / self.VERSION_FILE_NAME
        stored_version = version_path.read_text(encoding="utf-8").strip() if version_path.exists() else ""
        self.requires_rebuild = stored_version != self.INDEX_SCHEMA_VERSION

        if self.requires_rebuild and self.index_path.exists():
            shutil.rmtree(self.index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)

        # 定义 Schema
        # content 字段使用 'raw' 分词器，因为我们已经通过 jieba 预分词
        # tantivy 的 SimpleAnalyzer 会对 'raw' 字段按空格分割 token
        schema_builder = tantivy.SchemaBuilder()
        schema_builder.add_text_field("id", stored=True, tokenizer_name="raw")
        schema_builder.add_text_field("content", stored=True, tokenizer_name="raw")
        schema_builder.add_integer_field("owner_id", stored=True, indexed=True)
        self.schema = schema_builder.build()

        # 创建或加载索引
        self.index = tantivy.Index(schema=self.schema, path=str(self.index_path))

        self.writer = self.index.writer()
        self.writer.commit()

    def _ensure_writer(self):
        """确保 writer 可用，如果已被消耗则重新创建"""
        try:
            self.writer.commit()
        except Exception:
            self.writer = self.index.writer()

    def rebuild(self, memories: List[Dict]) -> None:
        """
        使用 SQLite 主数据全量重建当前版本的 BM25 索引。

        Args:
            memories: 记忆字典列表，每项包含 ``id``、``content`` 和 ``owner_id``。

        Returns:
            None: 索引提交并写入版本标记后直接返回。

        Raises:
            Exception: Tantivy 写入、提交或版本标记写入失败时抛出。
        """
        with self._lock:
            self._ensure_writer()
            for memory in memories:
                self.writer.add_document(tantivy.Document(
                    id=str(memory["id"]),
                    content=tokenize_chinese(str(memory["content"])),
                    owner_id=int(memory["owner_id"]),
                ))
            self._flush_writer()
            (self.index_path / self.VERSION_FILE_NAME).write_text(
                self.INDEX_SCHEMA_VERSION,
                encoding="utf-8",
            )
            self.requires_rebuild = False

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
        with self._lock:
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
        with self._lock:
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

            owner_query = tantivy.Query.term_query(
                self.schema,
                "owner_id",
                owner_id,
            )
            filtered_query = tantivy.Query.boolean_query([
                (tantivy.Occur.Must, parsed_query),
                (tantivy.Occur.Must, owner_query),
            ])
            results = []
            top_docs = searcher.search(filtered_query, limit=limit)

            for hit in top_docs.hits:
                score, doc_address = hit
                doc = searcher.doc(doc_address)
                results.append({
                    "id": doc.get_first("id") or "",
                    "score": score,
                    "content": doc.get_first("content") or "",
                })

            return results

    def delete_doc(self, memory_id: str) -> None:
        """
        删除文档

        Args:
            memory_id: 要删除的记忆 ID
        """
        with self._lock:
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
        with self._lock:
            self._ensure_writer()
            self._flush_writer()
            self.index.reload()
            searcher = self.index.searcher()

            if owner_id is not None:
                owner_query = tantivy.Query.term_query(self.schema, "owner_id", owner_id)
                return searcher.search(owner_query, limit=1).count

            return searcher.num_docs
