
import asyncio
import re

from app.services.embedding_service import get_embedding_service
from app.services.llm_service import get_llm_service
from app.services.vector_service import VectorService


# Initial heuristic; evaluate and tune with real questions later.
MAX_COSINE_DISTANCE = 0.9591


class RAGService:
    def __init__(
        self,
        vector_service=None,
        embedding_service=None,
        llm_service=None,
    ):
        self.vector_service = vector_service or VectorService()
        self.embedding_service = embedding_service
        self.llm_service = llm_service

    async def answer_question(
        self,
        question: str,
        document_id: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict:
        question = question.strip()
        history = history or []

        if not question:
            raise ValueError("Question cannot be empty.")

        if not document_id.strip():
            raise ValueError("Document ID cannot be empty.")

        embedding_service = (
            self.embedding_service or get_embedding_service()
        )
        llm_service = self.llm_service or get_llm_service()

        # Step 1: Rewrite follow-up questions using conversation history.
        retrieval_query = await asyncio.to_thread(
            llm_service.rewrite_retrieval_query,
            question,
            history,
        )

        if not retrieval_query or not retrieval_query.strip():
            retrieval_query = question

        print("Original question:", question)
        print("Conversation history:", history)
        print("Rewritten query:", retrieval_query)

        # Step 2: Embed the rewritten query.
        query_embedding = await asyncio.to_thread(
            embedding_service.embed_query,
            retrieval_query,
        )

        # Step 3: Retrieve passages from the selected document only.
        matches = await asyncio.to_thread(
            self.vector_service.search,
            query_embedding,
            5,
            document_id,
        )

        if not matches:
            return {
                "answer": (
                    "I couldn't find relevant passages in this document "
                    "to answer your question."
                ),
                "sources": [],
            }

        # Step 4: Check the closest match against the configured threshold.
        best_distance = min(item["distance"] for item in matches)

        print(
            f"Best cosine distance: {best_distance:.4f}, "
            f"threshold: {MAX_COSINE_DISTANCE}"
        )
        print("Retrieved passages:")

        for match in matches:
            print(
                "Distance:", match["distance"],
                "| Page:", match["metadata"]["page_number"],
                "| Text:", match["text"][:300],
            )

        if best_distance > MAX_COSINE_DISTANCE:
            return {
                "answer": (
                    "The document does not appear to contain enough "
                    "relevant information to answer this question."
                ),
                "sources": [],
            }

        # Step 5: Build numbered context and source metadata.
        sources = []
        context_parts = []

        for index, match in enumerate(matches, start=1):
            metadata = match["metadata"]

            source = {
                "citation_id": index,
                "document_id": metadata["document_id"],
                "filename": metadata["filename"],
                "page_number": metadata["page_number"],
                "chunk_index": metadata["chunk_index"],
            }

            sources.append(source)

            context_parts.append(
                f"[{index}] Filename: {source['filename']}; "
                f"page: {source['page_number']}\n"
                f"{match['text']}"
            )

        context = "\n\n".join(context_parts)

        # Step 6: Generate an answer using the original question,
        # retrieved PDF excerpts, and conversation history.
        answer = await asyncio.to_thread(
            llm_service.generate_answer,
            question,
            context,
            history,
        )

        # Step 7: Return only sources cited in the generated answer.
        cited_ids = {
            int(citation)
            for citation in re.findall(r"\[(\d+)\]", answer)
        }

        source_by_id = {
            source["citation_id"]: source
            for source in sources
        }

        cited_sources = [
            source_by_id[citation_id]
            for citation_id in sorted(cited_ids)
            if citation_id in source_by_id
        ]

        return {
            "answer": answer,
            "sources": cited_sources,
        }
