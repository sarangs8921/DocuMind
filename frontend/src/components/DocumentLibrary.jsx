
import { useEffect, useRef, useState } from "react";
import { getDocuments, uploadDocument, deleteDocument } from "../services/api";
import {
  FileText,
  Upload,
  RefreshCw,
  Trash2,
  CheckCircle2,
  AlertCircle,
  LoaderCircle,
} from "lucide-react";
import "./DocumentLibrary.css";

function DocumentLibrary({ selectedDocument, onSelectDocument }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingDocumentId, setDeletingDocumentId] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const fileInputRef = useRef(null);

  async function loadDocuments() {
    try {
      setError("");
      const data = await getDocuments();
      setDocuments(data);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Could not load documents. Check whether FastAPI is running."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDocuments();
  }, []);

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    event.target.value = "";

    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please select a PDF file.");
      return;
    }

    if (file.size > 20 * 1024 * 1024) {
      setError("The maximum file size is 20 MiB.");
      return;
    }

    setUploading(true);
    setError("");
    setSuccess("");

    try {
      const uploaded = await uploadDocument(file);
      setSuccess(`${uploaded.filename} uploaded successfully.`);
      await loadDocuments();
      onSelectDocument(uploaded);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Upload failed. Please try again."
      );
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(document) {
    const confirmed = window.confirm(
      `Delete "${document.filename}"?\n\nThis will permanently delete the PDF, its indexed content, and its chat history.`
    );

    if (!confirmed) return;

    setDeletingDocumentId(document.document_id);
    setError("");
    setSuccess("");

    try {
      await deleteDocument(document.document_id);

      setDocuments((current) =>
        current.filter(
          (item) => item.document_id !== document.document_id
        )
      );

      if (
        selectedDocument?.document_id === document.document_id
      ) {
        onSelectDocument(null);
      }

      setSuccess(`${document.filename} was deleted successfully.`);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Could not delete the document. Please try again."
      );
    } finally {
      setDeletingDocumentId(null);
    }
  }

  const busy = uploading || deletingDocumentId !== null;

  return (
    <aside className="document-library">
      <div className="library-heading">
        <div>
          <h2>Documents</h2>
          <p>Your PDF workspace</p>
        </div>

        <button
          type="button"
          className="icon-button"
          onClick={loadDocuments}
          disabled={loading || busy}
          aria-label="Refresh documents"
          title="Refresh documents"
        >
          <RefreshCw size={18} />
        </button>
      </div>

      <button
        type="button"
        className="upload-button"
        onClick={() => fileInputRef.current?.click()}
        disabled={busy}
      >
        {uploading ? (
          <LoaderCircle className="spin" size={18} />
        ) : (
          <Upload size={18} />
        )}
        {uploading ? "Processing PDF..." : "Upload PDF"}
      </button>

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,application/pdf"
        hidden
        onChange={handleUpload}
      />

      {uploading && (
        <p className="upload-hint">
          Extracting text and generating embeddings. Larger PDFs may take a
          little time.
        </p>
      )}

      {error && (
        <div className="library-message error-message" role="alert">
          <AlertCircle size={17} />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="library-message success-message" role="status">
          <CheckCircle2 size={17} />
          <span>{success}</span>
        </div>
      )}

      <div className="document-list">
        {loading ? (
          <p className="empty-state">Loading documents...</p>
        ) : documents.length === 0 ? (
          <div className="empty-state">
            <FileText size={32} />
            <p>No documents yet</p>
            <span>Upload a PDF to start chatting.</span>
          </div>
        ) : (
          documents.map((document) => {
            const isSelected =
              selectedDocument?.document_id === document.document_id;
            const isDeleting =
              deletingDocumentId === document.document_id;

            return (
              <div
                key={document.document_id}
                className={`document-row ${
                  isSelected ? "selected" : ""
                }`}
              >
                <button
                  type="button"
                  className={`document-card ${
                    isSelected ? "selected" : ""
                  }`}
                  onClick={() => onSelectDocument(document)}
                  disabled={busy}
                  aria-pressed={isSelected}
                >
                  <FileText size={21} className="document-icon" />

                  <span className="document-details">
                    <span className="document-name">
                      {document.filename}
                    </span>

                    <span className="document-meta">
                      {document.page_count} pages · {document.chunk_count} chunks
                    </span>

                    <span className="document-status">
                      {document.status}
                    </span>
                  </span>
                </button>

                <button
                  type="button"
                  className="delete-document-button"
                  onClick={() => handleDelete(document)}
                  disabled={busy}
                  aria-label={`Delete ${document.filename}`}
                  title={`Delete ${document.filename}`}
                >
                  {isDeleting ? (
                    <LoaderCircle className="spin" size={17} />
                  ) : (
                    <Trash2 size={17} />
                  )}
                </button>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}

export default DocumentLibrary;
