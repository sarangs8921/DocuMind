
import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000/api",
  timeout: 60000,
});

// Upload a PDF document
export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post("/documents/upload", formData);
  return response.data;
}

// Fetch all uploaded documents
export async function getDocuments() {
  const response = await api.get("/documents");
  return response.data;
}

// Delete an uploaded PDF document
export async function deleteDocument(documentId) {
  const response = await api.delete(`/documents/${documentId}`);
  return response.data;
}

// Ask a question about a selected PDF
export async function askQuestion({
  documentId,
  question,
  conversationId,
}) {
  const response = await api.post("/chat/ask", {
    document_id: documentId,
    question,
    ...(conversationId
      ? { conversation_id: conversationId }
      : {}),
  });

  return response.data;
}

// Fetch conversation history for a document
export async function getConversations(documentId) {
  const response = await api.get("/chat/conversations", {
    params: {
      document_id: documentId,
    },
  });

  return response.data;
}

// Fetch messages from a particular conversation
export async function getMessages(conversationId) {
  const response = await api.get(
    `/chat/conversations/${conversationId}/messages`
  );

  return response.data;
}

export default api;
