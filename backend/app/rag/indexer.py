from pathlib import Path
import re

from app.core.config import settings
from app.rag.embeddings import create_embedding_service
from app.rag.milvus_store import MilvusLiteStore
from app.rag.schemas import DOC_TYPE_LABELS, KnowledgeChunk, ROLE_PROFILES


SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def _resolve_doc_type(section_title: str) -> str:
    lowered = section_title.strip().lower()
    if "jd" in lowered:
        return "jd"
    if "必备技能" in section_title:
        return "skills"
    if "常见面试题" in section_title:
        return "questions"
    if "考察" in section_title or "维度" in section_title:
        return "rubric"
    return "jd"


def _split_sections(content: str) -> list[tuple[str, str]]:
    matches = list(SECTION_RE.finditer(content))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        if body:
            sections.append((title, body))
    return sections


def load_knowledge_chunks() -> list[KnowledgeChunk]:
    knowledge_root = settings.rag_knowledge_path / "roles"
    chunks: list[KnowledgeChunk] = []
    for file_path in sorted(knowledge_root.glob("*.md")):
        role_slug = file_path.stem
        role_profile = ROLE_PROFILES.get(role_slug)
        if role_profile is None:
            continue
        content = file_path.read_text(encoding="utf-8")
        for index, (section_title, body) in enumerate(_split_sections(content), start=1):
            doc_type = _resolve_doc_type(section_title)
            labeled_content = "\n".join(
                [
                    f"岗位：{role_profile.display_name}",
                    f"文档类型：{DOC_TYPE_LABELS.get(doc_type, doc_type)}",
                    f"章节：{section_title}",
                    body,
                ]
            ).strip()
            chunks.append(
                KnowledgeChunk(
                    id=f"{role_slug}-{doc_type}-{index}",
                    role_slug=role_slug,
                    role_name=role_profile.display_name,
                    doc_type=doc_type,
                    section_title=section_title,
                    content=labeled_content,
                    source_path=str(file_path.relative_to(settings.rag_knowledge_path)),
                )
            )
    return chunks


def rebuild_role_knowledge_index() -> dict[str, int]:
    chunks = load_knowledge_chunks()
    embedding_service = create_embedding_service()
    embeddings = embedding_service.embed_documents([item.content for item in chunks])
    for chunk, vector in zip(chunks, embeddings, strict=False):
        chunk.embedding = vector
    store = MilvusLiteStore()
    store.rebuild_collection(chunks, dimension=embedding_service.dimension)
    return {
        "document_count": len(list((settings.rag_knowledge_path / "roles").glob("*.md"))),
        "chunk_count": len(chunks),
        "dimension": embedding_service.dimension,
    }
