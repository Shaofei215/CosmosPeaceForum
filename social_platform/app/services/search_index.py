# 平台 Tantivy BM25 搜索索引
# 索引是主业务数据库的可重建投影，不作为事实存储。
import logging
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from social_platform.app.core.paths import get_search_index_dir
from social_platform.app.models.post import Post
from social_platform.app.models.user import User
from social_platform.app.services.search_tokenizer import (
    tokenize_text,
    tokenize_username,
    tokens_to_tantivy_text,
)

import tantivy


logger = logging.getLogger(__name__)


@dataclass
class SearchHit:
    id: int
    score: float


class _BaseTantivyIndex:
    def __init__(self, name: str):
        self.name = name
        self.index_path = Path(get_search_index_dir()) / name
        self._lock = threading.Lock()
        self.index = None
        self.writer = None
        self._needs_reload = False
        self._needs_rebuild = not self.index_path.exists() or not any(self.index_path.iterdir())

        self._open_or_create()

    @property
    def available(self) -> bool:
        return self.index is not None

    def exists(self) -> bool:
        return not self._needs_rebuild

    def _build_schema(self):
        raise NotImplementedError

    def _open_or_create(self) -> None:
        schema = self._build_schema()
        self.index_path.mkdir(parents=True, exist_ok=True)
        self.index = tantivy.Index(schema=schema, path=str(self.index_path))
        self.writer = self.index.writer()
        self.writer.commit()

    def rebuild(self, rows: Iterable[object]) -> None:
        with self._lock:
            if self.index_path.exists():
                shutil.rmtree(self.index_path)
            self._open_or_create()
            for row in rows:
                self._add_document(row)
            self._flush_writer()
            self._needs_rebuild = False

    def upsert(self, row: object) -> None:
        if not self.available:
            return

        row_id = getattr(row, "id", None)
        if row_id is None:
            return

        with self._lock:
            self._ensure_writer()
            self.writer.delete_documents("id", str(row_id))
            self._add_document(row)
            self._flush_writer()

    def delete(self, row_id: int) -> None:
        if not self.available:
            return

        with self._lock:
            self._ensure_writer()
            self.writer.delete_documents("id", str(row_id))
            self._flush_writer()

    def search(self, query: str, limit: int) -> List[SearchHit]:
        if not self.available:
            return []

        query_text = self._tokenize_query(query)
        if not query_text:
            return []

        with self._lock:
            if self._needs_reload:
                self.index.reload()
                self._needs_reload = False
            searcher = self.index.searcher()
            try:
                parsed_query, _ = self.index.parse_query_lenient(query_text, self._query_fields())
            except Exception as exc:
                logger.warning("解析搜索查询失败: %s", exc)
                return []

            try:
                top_docs = searcher.search(parsed_query, limit=limit)
            except Exception as exc:
                logger.warning("执行搜索失败: %s", exc)
                return []

            results: List[SearchHit] = []
            for score, doc_address in top_docs.hits:
                doc = searcher.doc(doc_address)
                raw_id = doc.get_first("id")
                if raw_id is None:
                    continue
                results.append(SearchHit(id=int(raw_id), score=float(score)))
            return results

    def _ensure_writer(self) -> None:
        try:
            self.writer.commit()
        except Exception:
            self.writer = self.index.writer()

    def _flush_writer(self) -> None:
        self.writer.commit()
        try:
            self.writer.wait_merging_threads()
        except Exception:
            pass
        self.writer = self.index.writer()
        self._needs_reload = True

    def _add_document(self, row: object) -> None:
        raise NotImplementedError

    def _query_fields(self) -> List[str]:
        raise NotImplementedError

    def _tokenize_query(self, query: str) -> str:
        raise NotImplementedError


class ContentSearchIndex(_BaseTantivyIndex):
    def __init__(self):
        super().__init__("content")

    def _build_schema(self):
        schema_builder = tantivy.SchemaBuilder()
        schema_builder.add_text_field("id", stored=True, tokenizer_name="raw")
        schema_builder.add_text_field("title", stored=True, tokenizer_name="raw")
        schema_builder.add_text_field("content", stored=True, tokenizer_name="raw")
        return schema_builder.build()

    def _add_document(self, row: Post) -> None:
        title_tokens = tokenize_text(row.title or "")
        content_tokens = tokenize_text(row.content or "")
        self.writer.add_document(tantivy.Document(
            id=str(row.id),
            title=title_tokens,
            content=content_tokens,
        ))

    def _query_fields(self) -> List[str]:
        return ["title", "content"]

    def _tokenize_query(self, query: str) -> str:
        return tokens_to_tantivy_text(tokenize_text(query))


class UserSearchIndex(_BaseTantivyIndex):
    def __init__(self):
        super().__init__("user")

    def _build_schema(self):
        schema_builder = tantivy.SchemaBuilder()
        schema_builder.add_text_field("id", stored=True, tokenizer_name="raw")
        schema_builder.add_text_field("username", stored=True, tokenizer_name="raw")
        return schema_builder.build()

    def _add_document(self, row: User) -> None:
        if not row.username:
            return
        self.writer.add_document(tantivy.Document(
            id=str(row.id),
            username=tokenize_username(row.username),
        ))

    def _query_fields(self) -> List[str]:
        return ["username"]

    def _tokenize_query(self, query: str) -> str:
        return tokens_to_tantivy_text(tokenize_username(query))


_content_index: Optional[ContentSearchIndex] = None
_user_index: Optional[UserSearchIndex] = None


def get_content_index() -> ContentSearchIndex:
    global _content_index
    if _content_index is None:
        _content_index = ContentSearchIndex()
    return _content_index


def get_user_index() -> UserSearchIndex:
    global _user_index
    if _user_index is None:
        _user_index = UserSearchIndex()
    return _user_index
