
import asyncio
from io import BytesIO

import pytest
from fastapi import UploadFile
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.services.document_service as document_service
from app.db.database import Base
from app.db.models import Document


class FakeEmbeddingService:
    def embed_texts(self, texts):
        return [[0.1] * 384 for _ in texts]


class FakeVectorService:
    def __init__(self, fail_on_add=False):
        self.fail_on_add = fail_on_add
        self.deleted_documents = []

    def add_chunks(self, document_id, filename, chunks, embeddings):
        if self.fail_on_add:
            raise RuntimeError("Simulated vector storage failure")
        return len(chunks)

    def delete_document(self, document_id):
        self.deleted_documents.append(document_id)


@pytest.fixture
def setup_service(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    test_session = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    monkeypatch.setattr(document_service, "SessionLocal", test_session)
    monkeypatch.setattr(document_service, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(
        document_service,
        "get_embedding_service",
        lambda: FakeEmbeddingService(),
    )
    monkeypatch.setattr(
        document_service,
        "extract_pdf_pages",
        lambda path: [
            {"page_number": 1, "text": "A" * 1200}
        ],
    )

    yield test_session

    engine.dispose()


def make_upload(filename="sample.pdf", content=b"%PDF-1.4\nexample"):
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
    )


def test_successful_upload_saves_metadata(setup_service):
    vector = FakeVectorService()
    service = document_service.DocumentService(vector_service=vector)

    result = asyncio.run(service.ingest_pdf(make_upload()))

    assert result["status"] == "indexed"
    assert result["filename"] == "sample.pdf"
    assert result["chunk_count"] == 2

    with setup_service() as db:
        record = db.scalar(
            select(Document).where(Document.id == result["document_id"])
        )

    assert record is not None
    assert record.filename == "sample.pdf"
    assert record.status == "indexed"
    assert record.chunk_count == 2


def test_non_pdf_is_rejected(setup_service):
    service = document_service.DocumentService(
        vector_service=FakeVectorService()
    )

    with pytest.raises(ValueError, match="Only PDF"):
        asyncio.run(service.ingest_pdf(make_upload("notes.txt")))


def test_invalid_pdf_signature_is_rejected(setup_service):
    service = document_service.DocumentService(
        vector_service=FakeVectorService()
    )

    with pytest.raises(ValueError, match="not a valid PDF"):
        asyncio.run(
            service.ingest_pdf(
                make_upload(content=b"This is plain text")
            )
        )


def test_oversized_upload_is_rejected_and_cleaned(setup_service):
    service = document_service.DocumentService(
        vector_service=FakeVectorService()
    )
    content = b"%PDF-" + b"A" * document_service.MAX_FILE_SIZE

    with pytest.raises(ValueError, match="20 MiB"):
        asyncio.run(
            service.ingest_pdf(make_upload(content=content))
        )

    assert list(document_service.UPLOAD_DIR.iterdir()) == []


def test_vector_failure_does_not_save_metadata(setup_service):
    vector = FakeVectorService(fail_on_add=True)
    service = document_service.DocumentService(vector_service=vector)

    with pytest.raises(RuntimeError, match="Simulated"):
        asyncio.run(service.ingest_pdf(make_upload()))

    with setup_service() as db:
        records = db.scalars(select(Document)).all()

    assert records == []
    assert len(vector.deleted_documents) == 1
    assert list(document_service.UPLOAD_DIR.iterdir()) == []
