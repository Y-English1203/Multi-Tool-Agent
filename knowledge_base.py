"""知识库管理。

* PDF 文档存放在 ``knowledge/``；
* 向量索引持久化到 ``chroma_db/``；
* 文档登记信息保存在 ``knowledge.db``；
* 首次启动自动把项目根目录的 ``test.pdf`` 收录为《京东集团员工手册》。

索引只在文档内容变化时重建，避免每次启动重复 Embedding。
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader

BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "knowledge"
CHROMA_DIR = BASE_DIR / "chroma_db"
REGISTRY_DB = BASE_DIR / "knowledge.db"

EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
COLLECTION_NAME = "enterprise_knowledge"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80

DEFAULT_PDF = BASE_DIR / "test.pdf"
DEFAULT_PDF_NAME = "京东集团员工手册.pdf"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _doc_id(filename: str) -> str:
    return hashlib.sha1(filename.encode("utf-8")).hexdigest()[:12]


class KnowledgeBase:
    def __init__(
        self,
        docs_dir: Path = DOCS_DIR,
        chroma_dir: Path = CHROMA_DIR,
        registry_db: Path = REGISTRY_DB,
    ) -> None:
        self.docs_dir = docs_dir
        self.chroma_dir = chroma_dir
        self.registry_db = registry_db

        self.embeddings = None
        self.vectorstore = None
        self.error: str | None = None
        self.ready = False
        self.model_name = EMBEDDING_MODEL

        self._lock = threading.Lock()
        self._init_dirs()

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------
    def _init_dirs(self) -> None:
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.registry_db) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT UNIQUE NOT NULL,
                    sha256 TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    pages INTEGER NOT NULL,
                    chunks INTEGER NOT NULL,
                    indexed_at TEXT NOT NULL
                )
                """
            )

    def _ensure_default_document(self) -> None:
        has_pdf = any(self.docs_dir.glob("*.pdf"))
        if not has_pdf and DEFAULT_PDF.exists():
            target = self.docs_dir / DEFAULT_PDF_NAME
            if not target.exists():
                shutil.copy2(DEFAULT_PDF, target)
                print(f"[Knowledge] 已收录默认文档：{target.name}")

    def initialize(self) -> None:
        """加载模型并同步索引。失败时记录错误，服务仍可启动。"""
        try:
            from langchain_chroma import Chroma
            from langchain_huggingface import HuggingFaceEmbeddings

            self._ensure_default_document()

            print(f"[Knowledge] 正在加载 Embedding 模型：{EMBEDDING_MODEL}")
            self.embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )

            self.vectorstore = Chroma(
                collection_name=COLLECTION_NAME,
                embedding_function=self.embeddings,
                persist_directory=str(self.chroma_dir),
                collection_metadata={"hnsw:space": "cosine"},
            )

            self.sync()
            self.ready = True
            self.error = None
            print(
                f"[Knowledge] 就绪：{self.stats()['documents']} 个文档，"
                f"{self.stats()['chunks']} 个切片"
            )
        except Exception as exc:  # 模型缺失 / 离线 / Chroma 异常
            self.ready = False
            self.error = str(exc)
            print(f"[Knowledge] 初始化失败：{exc}")

    # ------------------------------------------------------------------
    # 文档同步
    # ------------------------------------------------------------------
    def _read_registry(self) -> dict[str, dict[str, Any]]:
        with sqlite3.connect(self.registry_db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM documents").fetchall()
        return {row["id"]: dict(row) for row in rows}

    def _write_registry(self, row: dict[str, Any]) -> None:
        with sqlite3.connect(self.registry_db) as conn:
            conn.execute(
                """
                INSERT INTO documents
                    (id, filename, sha256, size, pages, chunks, indexed_at)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    filename=excluded.filename,
                    sha256=excluded.sha256,
                    size=excluded.size,
                    pages=excluded.pages,
                    chunks=excluded.chunks,
                    indexed_at=excluded.indexed_at
                """,
                (
                    row["id"],
                    row["filename"],
                    row["sha256"],
                    row["size"],
                    row["pages"],
                    row["chunks"],
                    row["indexed_at"],
                ),
            )

    def _remove_registry(self, doc_id: str) -> None:
        with sqlite3.connect(self.registry_db) as conn:
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

    def _delete_chunks(self, doc_id: str) -> None:
        if not self.vectorstore:
            return
        try:
            existing = self.vectorstore.get(where={"doc_id": doc_id})
            ids = existing.get("ids") or []
            if ids:
                self.vectorstore.delete(ids=ids)
        except Exception as exc:
            print(f"[Knowledge] 删除旧切片失败：{exc}")

    def _parse_pdf(self, path: Path) -> tuple[list[Any], int]:
        from langchain_core.documents import Document
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        reader = PdfReader(str(path))
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", "。", "；", "，", " ", ""],
        )

        doc_id = _doc_id(path.name)
        chunks: list[Any] = []
        pages_with_text = 0

        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            pages_with_text += 1
            for index, piece in enumerate(splitter.split_text(text)):
                if not piece.strip():
                    continue
                chunks.append(
                    Document(
                        page_content=piece.strip(),
                        metadata={
                            "doc_id": doc_id,
                            "source": path.name,
                            "page": page_number,
                            "chunk": index,
                        },
                    )
                )

        return chunks, pages_with_text

    def _index_file(self, path: Path, force: bool = False) -> dict[str, Any]:
        if not self.vectorstore:
            raise RuntimeError("知识库尚未初始化")

        doc_id = _doc_id(path.name)
        digest = _sha256(path)
        registry = self._read_registry()
        existing = registry.get(doc_id)

        if (
            existing
            and existing["sha256"] == digest
            and existing["size"] == path.stat().st_size
            and not force
        ):
            return existing

        chunks, pages = self._parse_pdf(path)
        if not chunks:
            raise ValueError(f"文档中没有可提取的文字：{path.name}")

        self._delete_chunks(doc_id)
        ids = [f"{doc_id}-{index}" for index in range(len(chunks))]
        self.vectorstore.add_documents(chunks, ids=ids)

        row = {
            "id": doc_id,
            "filename": path.name,
            "sha256": digest,
            "size": path.stat().st_size,
            "pages": pages,
            "chunks": len(chunks),
            "indexed_at": _now(),
        }
        self._write_registry(row)
        print(
            f"[Knowledge] 已索引 {path.name}：{pages} 页，{len(chunks)} 个切片"
        )
        return row

    def sync(self, force: bool = False) -> None:
        if not self.vectorstore:
            return

        with self._lock:
            self._ensure_default_document()
            registered = self._read_registry()
            files = sorted(self.docs_dir.glob("*.pdf"))
            filenames = {path.name for path in files}

            # 删除已不存在的文档
            for doc_id, row in registered.items():
                if row["filename"] not in filenames:
                    self._delete_chunks(doc_id)
                    self._remove_registry(doc_id)
                    print(f"[Knowledge] 已移除文档索引：{row['filename']}")

            for path in files:
                try:
                    self._index_file(path, force=force)
                except Exception as exc:
                    print(f"[Knowledge] 索引 {path.name} 失败：{exc}")

            self._refresh_chunk_counts()

    def _refresh_chunk_counts(self) -> None:
        if not self.vectorstore:
            return
        try:
            ids = self.vectorstore.get().get("ids") or []
        except Exception:
            return

        counts: dict[str, int] = {}
        for item_id in ids:
            doc_id = str(item_id).split("-", 1)[0]
            counts[doc_id] = counts.get(doc_id, 0) + 1

        with sqlite3.connect(self.registry_db) as conn:
            for doc_id, count in counts.items():
                conn.execute(
                    "UPDATE documents SET chunks = ? WHERE id = ?",
                    (count, doc_id),
                )

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    def list_documents(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.registry_db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY indexed_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def add_document(self, source_path: Path, filename: str) -> dict[str, Any]:
        """把上传的 PDF 复制进 knowledge/ 并建立索引。"""
        if not filename.lower().endswith(".pdf"):
            raise ValueError("目前只支持 PDF 文档")

        safe_name = Path(filename).name
        target = self.docs_dir / safe_name

        # 校验是否为有效 PDF
        try:
            reader = PdfReader(str(source_path))
            _ = len(reader.pages)
        except Exception as exc:
            raise ValueError(f"无法解析 PDF：{exc}") from exc

        shutil.copy2(source_path, target)

        with self._lock:
            row = self._index_file(target, force=True)
        return row

    def delete_document(self, doc_id: str) -> bool:
        registry = self._read_registry()
        row = registry.get(doc_id)
        if not row:
            return False

        with self._lock:
            self._delete_chunks(doc_id)
            path = self.docs_dir / row["filename"]
            if path.exists():
                path.unlink()
            self._remove_registry(doc_id)
        return True

    def rebuild(self) -> None:
        """清空向量集合后重新索引全部文档。"""
        if not self.vectorstore:
            raise RuntimeError("知识库尚未初始化")

        with self._lock:
            try:
                self.vectorstore.delete_collection()
            except Exception as exc:
                print(f"[Knowledge] 清空集合失败：{exc}")

            from langchain_chroma import Chroma

            self.vectorstore = Chroma(
                collection_name=COLLECTION_NAME,
                embedding_function=self.embeddings,
                persist_directory=str(self.chroma_dir),
                collection_metadata={"hnsw:space": "cosine"},
            )

            with sqlite3.connect(self.registry_db) as conn:
                conn.execute("DELETE FROM documents")

            for path in sorted(self.docs_dir.glob("*.pdf")):
                self._index_file(path, force=True)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not self.ready or not self.vectorstore:
            raise RuntimeError(self.error or "知识库尚未初始化")

        results = self.vectorstore.similarity_search_with_score(
            query, k=max(1, min(int(top_k or 5), 20))
        )

        items = []
        for doc, distance in results:
            # cosine 距离：0 最相关
            score = round(max(0.0, 1.0 - float(distance)), 4)
            items.append(
                {
                    "content": doc.page_content,
                    "source": doc.metadata.get("source", "未知文档"),
                    "page": doc.metadata.get("page"),
                    "score": score,
                }
            )
        return items

    def stats(self) -> dict[str, Any]:
        documents = self.list_documents()
        return {
            "ready": self.ready,
            "error": self.error,
            "documents": len(documents),
            "pages": sum(int(doc.get("pages") or 0) for doc in documents),
            "chunks": sum(int(doc.get("chunks") or 0) for doc in documents),
            "size": sum(int(doc.get("size") or 0) for doc in documents),
            "model": self.model_name,
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "persist_dir": str(self.chroma_dir),
        }

    def get_vectorstore(self):
        return self.vectorstore
