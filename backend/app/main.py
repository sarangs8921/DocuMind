from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.documents import router as documents_router
from contextlib import asynccontextmanager
from app.db.database import init_db
from app.api.routes.chat import router as chat_router
from app.core.config import APP_NAME

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title=APP_NAME,
    description="Chat with your PDFs using Retrieval-Augmented Generation.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(documents_router)
app.include_router(chat_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Welcome to DocuMind",
        "status": "running",
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "application": APP_NAME,
    }