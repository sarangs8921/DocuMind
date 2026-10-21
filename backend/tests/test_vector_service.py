
import pytest

from app.services.vector_service import VectorService


@pytest.fixture
def vector_service(tmp_path):
    return VectorService(storage_path=tmp_path / "chroma")


def test_add_and_search_chunks(vector_service):
    chunks = [
        {
            "chunk_index": 0,
            "page_number": 1,
            "text": "Machine learning models learn patterns from data.",
        },
        {
            "chunk_index": 1,
            "page_number": 2,
            "text": "The document explains how to bake chocolate cake.",
        },
    ]

    embeddings = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ]

    count = vector_service.add_chunks(
        document_id="test-document",
        filename="sample.pdf",
        chunks=chunks,
        embeddings=embeddings,
    )

    assert count == 2

    results = vector_service.search(
        query_embedding=[0.99, 0.01, 0.0],
        n_results=1,
        document_id="test-document",
    )

    assert len(results) == 1
    assert "Machine learning" in results[0]["text"]
    assert results[0]["metadata"]["filename"] == "sample.pdf"
    assert results[0]["metadata"]["page_number"] == 1


def test_search_empty_collection(vector_service):
    results = vector_service.search(
        query_embedding=[1.0, 0.0, 0.0]
    )

    assert results == []


def test_add_chunks_rejects_mismatched_embeddings(vector_service):
    chunks = [
        {
            "chunk_index": 0,
            "page_number": 1,
            "text": "Example text",
        }
    ]

    with pytest.raises(ValueError, match="one embedding"):
        vector_service.add_chunks(
            document_id="test-document",
            filename="sample.pdf",
            chunks=chunks,
            embeddings=[],
        )


def test_delete_document(vector_service):
    chunks = [
        {
            "chunk_index": 0,
            "page_number": 1,
            "text": "Document to delete",
        }
    ]

    vector_service.add_chunks(
        document_id="delete-me",
        filename="delete.pdf",
        chunks=chunks,
        embeddings=[[1.0, 0.0, 0.0]],
    )

    vector_service.delete_document("delete-me")

    results = vector_service.search(
        query_embedding=[1.0, 0.0, 0.0],
        document_id="delete-me",
    )

    assert results == []
