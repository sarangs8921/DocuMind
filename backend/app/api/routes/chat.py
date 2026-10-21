
import json
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from groq import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import ChatMessage, Conversation, Document
from app.services.rag_service import RAGService


router = APIRouter(prefix="/api/chat", tags=["Chat"])


class AskRequest(BaseModel):
    document_id: UUID
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None


@router.post("/ask")
async def ask_question(request: AskRequest):
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="Question cannot be empty.",
        )

    document_id = str(request.document_id)

    with SessionLocal() as db:
        document = db.get(Document, document_id)

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Document not found.",
            )

        if document.status != "indexed":
            raise HTTPException(
                status_code=409,
                detail="Document is not ready for questions.",
            )

        if request.conversation_id:
            conversation_id = str(request.conversation_id)
            conversation = db.get(Conversation, conversation_id)

            if (
                conversation is None
                or conversation.document_id != document_id
            ):
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found for this document.",
                )
        else:
            conversation_id = str(uuid4())
            conversation = Conversation(
                id=conversation_id,
                document_id=document_id,
                title=question[:80],
            )
            db.add(conversation)
            db.commit()

        # Load the previous six messages BEFORE saving the new question.
        previous_messages = db.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.conversation_id == conversation_id
            )
            .order_by(
                ChatMessage.created_at.desc(),
                ChatMessage.id.desc(),
            )
            .limit(6)
        ).all()

        previous_messages.reverse()

        history = [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in previous_messages
            if message.role in {"user", "assistant"}
        ]

        # Save the current question after building history.
        db.add(
            ChatMessage(
                id=str(uuid4()),
                conversation_id=conversation_id,
                role="user",
                content=question,
            )
        )
        db.commit()

    try:
        service = RAGService()

        result = await service.answer_question(
            question=question,
            document_id=document_id,
            history=history,
        )

    except (APIConnectionError, APITimeoutError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to reach the LLM provider. Please try again.",
        ) from exc

    except APIStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail="The LLM provider rejected or failed the request.",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Question answering failed.",
        ) from exc

    with SessionLocal() as db:
        db.add(
            ChatMessage(
                id=str(uuid4()),
                conversation_id=conversation_id,
                role="assistant",
                content=result["answer"],
                sources_json=json.dumps(result["sources"]),
            )
        )
        db.commit()

    return {
        "conversation_id": conversation_id,
        "document_id": document_id,
        "answer": result["answer"],
        "sources": result["sources"],
    }


@router.get("/conversations")
def list_conversations(document_id: UUID):
    with SessionLocal() as db:
        document = db.get(Document, str(document_id))

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Document not found.",
            )

        conversations = db.scalars(
            select(Conversation)
            .where(
                Conversation.document_id == str(document_id)
            )
            .order_by(Conversation.created_at.desc())
        ).all()

        return [
            {
                "conversation_id": conversation.id,
                "document_id": conversation.document_id,
                "title": conversation.title,
                "created_at": conversation.created_at.isoformat(),
            }
            for conversation in conversations
        ]


@router.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(conversation_id: UUID):
    with SessionLocal() as db:
        conversation = db.get(
            Conversation,
            str(conversation_id),
        )

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        messages = db.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.conversation_id == str(conversation_id)
            )
            .order_by(
                ChatMessage.created_at,
                ChatMessage.id,
            )
        ).all()

        return {
            "conversation_id": conversation.id,
            "document_id": conversation.document_id,
            "messages": [
                {
                    "message_id": message.id,
                    "role": message.role,
                    "content": message.content,
                    "sources": (
                        json.loads(message.sources_json)
                        if message.sources_json
                        else []
                    ),
                    "created_at": message.created_at.isoformat(),
                }
                for message in messages
            ],
        }
