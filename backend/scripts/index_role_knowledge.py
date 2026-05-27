from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rag.indexer import rebuild_role_knowledge_index  # noqa: E402


def main() -> None:
    result = rebuild_role_knowledge_index()
    print("Role knowledge index rebuilt successfully.")
    print(f"Documents: {result['document_count']}")
    print(f"Chunks: {result['chunk_count']}")
    print(f"Dimension: {result['dimension']}")


if __name__ == "__main__":
    main()
