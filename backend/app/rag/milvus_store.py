from typing import Any

from app.core.config import settings
from app.rag.schemas import KnowledgeChunk, RetrievedChunk

try:
    from pymilvus import DataType, MilvusClient
except ImportError:  # pragma: no cover - depends on optional runtime dependency
    DataType = None  # type: ignore[assignment]
    MilvusClient = None  # type: ignore[assignment]


class MilvusLiteStore:
    def __init__(self) -> None:
        if MilvusClient is None or DataType is None:
            raise RuntimeError("pymilvus[milvus-lite] 未安装，无法使用 Milvus Lite")
        self.collection_name = settings.rag_collection_name
        self._client = MilvusClient(str(settings.milvus_lite_db_file))

    def has_collection(self) -> bool:
        return self._client.has_collection(collection_name=self.collection_name)

    def rebuild_collection(self, chunks: list[KnowledgeChunk], *, dimension: int) -> None:
        if self.has_collection():
            self._client.drop_collection(collection_name=self.collection_name)
        schema = self._client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=128)
        schema.add_field(field_name="role_slug", datatype=DataType.VARCHAR, max_length=64)
        schema.add_field(field_name="role_name", datatype=DataType.VARCHAR, max_length=64)
        schema.add_field(field_name="doc_type", datatype=DataType.VARCHAR, max_length=32)
        schema.add_field(field_name="section_title", datatype=DataType.VARCHAR, max_length=128)
        schema.add_field(field_name="source_path", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=8192)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dimension)
        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_name="vector_idx",
            metric_type="COSINE",
            index_type="AUTOINDEX",
        )
        self._client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
        )
        if chunks:
            self._client.insert(
                collection_name=self.collection_name,
                data=[
                    {
                        "id": item.id,
                        "role_slug": item.role_slug,
                        "role_name": item.role_name,
                        "doc_type": item.doc_type,
                        "section_title": item.section_title,
                        "source_path": item.source_path,
                        "content": item.content,
                        "vector": item.embedding,
                    }
                    for item in chunks
                ],
            )
        self._client.load_collection(collection_name=self.collection_name)

    def search(self, *, query_vector: list[float], role_slug: str, limit: int) -> list[RetrievedChunk]:
        if not self.has_collection():
            return []
        search_result = self._client.search(
            collection_name=self.collection_name,
            data=[query_vector],
            filter=f"role_slug == '{role_slug}'",
            limit=limit,
            output_fields=["role_slug", "role_name", "doc_type", "section_title", "source_path", "content"],
        )
        rows = search_result[0] if search_result else []
        results: list[RetrievedChunk] = []
        for row in rows:
            entity = row.get("entity", {}) if isinstance(row, dict) else {}
            if not entity:
                continue
            results.append(
                RetrievedChunk(
                    id=str(row.get("id", "")),
                    role_slug=str(entity.get("role_slug", "")),
                    role_name=str(entity.get("role_name", "")),
                    doc_type=str(entity.get("doc_type", "")),
                    section_title=str(entity.get("section_title", "")),
                    source_path=str(entity.get("source_path", "")),
                    content=str(entity.get("content", "")),
                    score=float(row.get("distance", 0.0)),
                )
            )
        return results

    def close(self) -> None:
        close_fn = getattr(self._client, "close", None)
        if callable(close_fn):
            close_fn()
