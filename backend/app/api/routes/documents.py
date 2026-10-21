
from fastapi import APIRouter, File, HTTPException, UploadFile
from pypdf.errors import PdfReadError
from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Document
from app.services.document_service import DocumentService


router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/upload", status_code=201)
async def upload_document(file: UploadFile = File(...)):
    service = DocumentService()

    try:
        return await service.ingest_pdf(file)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except (PdfReadError, OSError) as exc:
        raise HTTPException(
            status_code=400,
            detail="The PDF could not be read or processed.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Document ingestion failed.",
        ) from exc


@router.get("")
def list_documents():
    with SessionLocal() as db:
        documents = db.scalars(
            select(Document).order_by(Document.created_at.desc())
        ).all()

        return [
            {
                "document_id": document.id,
                "filename": document.filename,
                "page_count": document.page_count,
                "chunk_count": document.chunk_count,
                "status": document.status,
                "created_at": document.created_at.isoformat(),
            }
            for document in documents
        ]


@router.delete("/{document_id}")
def delete_document(document_id: str):
    service = DocumentService()

    try:
        return service.delete_document(document_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Document deletion failed.",
        ) from exc
