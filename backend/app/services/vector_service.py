
from pathlib import Path

import chromadb


BACKEND_DIR = Path(__file__).resolve().parents[2]
CHROMA_DIR = BACKEND_DIR / "storage" / "chroma"


class VectorService:
    def __init__(self, storage_path: str | Path = CHROMA_DIR):
        path = Path(storage_path)
        path.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(path))

        self.collection = self.client.get_or_create_collection(
            name="documind_chunks",
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(
        self,
        document_id: str,
        filename: str,
        chunks: list[dict],
        embeddings: list[list[float]],
    ) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError("Each chunk must have one embedding.")

        if not chunks:
            return 0

        ids = [
            f"{document_id}_{chunk['chunk_index']}"
            for chunk in chunks
        ]

        documents = [chunk["text"] for chunk in chunks]

        metadatas = [
            {
                "document_id": document_id,
                "filename": filename,
                "page_number": chunk["page_number"],
                "chunk_index": chunk["chunk_index"],
            }
            for chunk in chunks
        ]

        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        return len(chunks)

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        document_id: str | None = None,
    ) -> list[dict]:
        if n_results <= 0:
            raise ValueError("n_results must be greater than zero.")

        if not query_embedding:
            raise ValueError("Query embedding cannot be empty.")

        total = self.collection.count()

        if total == 0:
            return []

        query_args = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, total),
            "include": ["documents", "metadatas", "distances"],
        }

        if document_id is not None:
            query_args["where"] = {"document_id": document_id}

        results = self.collection.query(**query_args)

        matches = []

        for index, text in enumerate(results["documents"][0]):
            matches.append({
                "text": text,
                "metadata": results["metadatas"][0][index],
                "distance": results["distances"][0][index],
            })

        return matches

    def delete_document(self, document_id: str) -> None:
        self.collection.delete(
            where={"document_id": document_id}
        )
