
import asyncio
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.db.database import SessionLocal
from app.db.models import Document
from app.services.chunking_service import chunk_pages
from app.services.embedding_service import get_embedding_service
from app.services.pdf_service import extract_pdf_pages
from app.services.vector_service import VectorService
from sqlalchemy import delete, select

from app.db.models import ChatMessage, Conversation, Document


BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BACKEND_DIR / "storage" / "uploads"
MAX_FILE_SIZE = 20 * 1024 * 1024


class DocumentService:
    def __init__(self, vector_service: VectorService | None = None):
        self.vector_service = vector_service or VectorService()

    async def ingest_pdf(self, file: UploadFile) -> dict:
        original_name = Path(file.filename or "").name

        if not original_name.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are supported.")

        if not original_name or original_name in {".", ".."}:
            raise ValueError("A valid filename is required.")

        document_id = str(uuid.uuid4())
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        stored_filename = f"{document_id}.pdf"
        destination = UPLOAD_DIR / stored_filename
        total_size = 0

        try:
            with destination.open("wb") as output:
                while True:
                    block = await file.read(1024 * 1024)

                    if not block:
                        break

                    total_size += len(block)

                    if total_size > MAX_FILE_SIZE:
                        raise ValueError(
                            "PDF exceeds the maximum size of 20 MiB."
                        )

                    output.write(block)

            if total_size == 0:
                raise ValueError("Uploaded file is empty.")

            with destination.open("rb") as source:
                if source.read(5) != b"%PDF-":
                    raise ValueError("The uploaded file is not a valid PDF.")

            pages = await asyncio.to_thread(
                extract_pdf_pages, destination
            )
            chunks = chunk_pages(pages)

            if not chunks:
                raise ValueError("No usable text chunks were extracted.")

            embedding_service = get_embedding_service()
            embeddings = await asyncio.to_thread(
                embedding_service.embed_texts,
                [chunk["text"] for chunk in chunks],
            )

            if len(embeddings) != len(chunks):
                raise RuntimeError("Embedding count does not match chunk count.")

            await asyncio.to_thread(
                self.vector_service.add_chunks,
                document_id,
                original_name,
                chunks,
                embeddings,
            )

            with SessionLocal() as db:
                document = Document(
                    id=document_id,
                    filename=original_name,
                    stored_filename=stored_filename,
                    file_size_bytes=total_size,
                    page_count=max(
                        page["page_number"] for page in pages
                    ),
                    chunk_count=len(chunks),
                    status="indexed",
                )
                db.add(document)
                db.commit()

            return {
                "document_id": document_id,
                "filename": original_name,
                "page_count": max(
                    page["page_number"] for page in pages
                ),
                "chunk_count": len(chunks),
                "status": "indexed",
            }

        except Exception:
            try:
                await asyncio.to_thread(
                    self.vector_service.delete_document, document_id
                )
            except Exception:
                # Cleanup failure should not hide the original error.
                pass

            destination.unlink(missing_ok=True)
            raise

        finally:
            await file.close()
    def delete_document(self, document_id: str) -> dict:
        # Verify that the document exists before deleting anything.
        with SessionLocal() as db:
            document = db.get(Document, document_id)

            if document is None:
                raise ValueError("Document not found.")

            stored_filename = document.stored_filename

        # Remove the document's vectors from ChromaDB.
        self.vector_service.delete_document(document_id)

        # Explicitly delete related messages and conversations.
        # This does not depend on SQLite foreign-key cascade settings.
        with SessionLocal() as db:
            document = db.get(Document, document_id)

            if document is None:
                raise ValueError("Document not found.")

            conversation_ids = db.scalars(
                select(Conversation.id).where(
                    Conversation.document_id == document_id
                )
            ).all()

            if conversation_ids:
                db.execute(
                    delete(ChatMessage).where(
                        ChatMessage.conversation_id.in_(conversation_ids)
                    )
                )

            db.execute(
                delete(Conversation).where(
                    Conversation.document_id == document_id
                )
            )

            db.delete(document)
            db.commit()

        # Remove the stored PDF after the database transaction succeeds.
        safe_filename = Path(stored_filename).name
        pdf_path = UPLOAD_DIR / safe_filename
        pdf_path.unlink(missing_ok=True)

        return {
            "document_id": document_id,
            "message": "Document and associated chat history deleted successfully.",
        }