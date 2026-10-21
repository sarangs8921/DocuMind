
import asyncio

from app.services.rag_service import RAGService


class FakeEmbeddingService:
    def embed_query(self, query):
        return [1.0, 0.0, 0.0]


class FakeVectorService:
    def __init__(self, matches):
        self.matches = matches
        self.last_document_id = None

    def search(self, query_embedding, n_results, document_id):
        self.last_document_id = document_id
        return self.matches


class FakeLLMService:
    def __init__(self):
        self.last_context = None

    def generate_answer(self, question, context):
        self.last_context = context
        return "The researchers used a controlled experiment [1]."


def make_match():
    return {
        "text": "The researchers used a controlled experiment.",
        "metadata": {
            "document_id": "document-123",
            "filename": "research.pdf",
            "page_number": 4,
            "chunk_index": 2,
        },
        "distance": 0.2,
    }


def test_answer_includes_source_metadata():
    vector = FakeVectorService([make_match()])
    llm = FakeLLMService()

    service = RAGService(
        vector_service=vector,
        embedding_service=FakeEmbeddingService(),
        llm_service=llm,
    )

    result = asyncio.run(
        service.answer_question(
            "What methodology was used?",
            "document-123",
        )
    )

    assert "controlled experiment" in result["answer"]
    assert result["sources"][0]["filename"] == "research.pdf"
    assert result["sources"][0]["page_number"] == 4
    assert "[1]" in llm.last_context
    assert vector.last_document_id == "document-123"


def test_no_matches_does_not_call_llm():
    vector = FakeVectorService([])
    llm = FakeLLMService()

    service = RAGService(
        vector_service=vector,
        embedding_service=FakeEmbeddingService(),
        llm_service=llm,
    )

    result = asyncio.run(
        service.answer_question("Explain the results.", "document-123")
    )

    assert result["sources"] == []
    assert "couldn't find relevant passages" in result["answer"]
    assert llm.last_context is None


def test_distant_matches_do_not_call_llm():
    match = make_match()
    match["distance"] = 0.95

    vector = FakeVectorService([match])
    llm = FakeLLMService()

    service = RAGService(
        vector_service=vector,
        embedding_service=FakeEmbeddingService(),
        llm_service=llm,
    )

    result = asyncio.run(
        service.answer_question("Explain the results.", "document-123")
    )

    assert result["sources"] == []
    assert "not appear to contain enough relevant information" in result["answer"]
    assert llm.last_context is None


def test_empty_question_is_rejected():
    service = RAGService(
        vector_service=FakeVectorService([]),
        embedding_service=FakeEmbeddingService(),
        llm_service=FakeLLMService(),
    )

    try:
        asyncio.run(service.answer_question("   ", "document-123"))
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Question cannot be empty" in str(exc)

def test_only_cited_sources_are_returned():
    matches = [
        make_match(),
        {
            **make_match(),
            "text": "React.js appears in the skills section.",
            "metadata": {
                "document_id": "document-123",
                "filename": "research.pdf",
                "page_number": 2,
                "chunk_index": 3,
            },
        },
    ]

    class CitingLLM:
        def generate_answer(self, question, context):
            return "The experience mentions React.js [1]."

    service = RAGService(
        vector_service=FakeVectorService(matches),
        embedding_service=FakeEmbeddingService(),
        llm_service=CitingLLM(),
    )

    result = asyncio.run(
        service.answer_question(
            "Does the document mention React.js?",
            "document-123",
        )
    )

    assert len(result["sources"]) == 1
    assert result["sources"][0]["citation_id"] == 1
    assert result["sources"][0]["chunk_index"] == 2
