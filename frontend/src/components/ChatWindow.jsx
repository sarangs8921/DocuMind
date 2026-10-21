
import { useEffect, useRef, useState } from "react";

import {
  ArrowUp,
  BookOpen,
  LoaderCircle,
  MessageSquare,
  Plus,
  UserRound,
  Bot,
  AlertCircle,
} from "lucide-react";

import {
  askQuestion,
  getConversations,
  getMessages,
} from "../services/api";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import "./ChatWindow.css";

function ChatWindow({ document }) {
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeCitation, setActiveCitation] = useState(null);

  const sourceRefs = useRef({});
  const highlightTimer = useRef(null);

  // Reset chat when the selected document changes.
  useEffect(() => {
    setConversations([]);
    setConversationId(null);
    setMessages([]);
    setQuestion("");
    setError("");
    setActiveCitation(null);
    sourceRefs.current = {};

    if (highlightTimer.current) {
      window.clearTimeout(highlightTimer.current);
      highlightTimer.current = null;
    }

    if (document?.document_id) {
      loadConversations(document.document_id);
    }

    return () => {
      if (highlightTimer.current) {
        window.clearTimeout(highlightTimer.current);
        highlightTimer.current = null;
      }
    };
  }, [document?.document_id]);

  // Clean up the highlight timer when the component unmounts.
  useEffect(() => {
    return () => {
      if (highlightTimer.current) {
        window.clearTimeout(highlightTimer.current);
      }
    };
  }, []);

  async function loadConversations(documentId) {
    setHistoryLoading(true);

    try {
      const data = await getConversations(documentId);
      setConversations(data);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Could not load conversation history."
      );
    } finally {
      setHistoryLoading(false);
    }
  }

  async function openConversation(id) {
    setConversationId(id);
    setMessages([]);
    setError("");
    setActiveCitation(null);
    setHistoryLoading(true);

    if (highlightTimer.current) {
      window.clearTimeout(highlightTimer.current);
      highlightTimer.current = null;
    }

    sourceRefs.current = {};

    try {
      const data = await getMessages(id);
      setMessages(data.messages || []);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Could not load this conversation."
      );
    } finally {
      setHistoryLoading(false);
    }
  }

  function startNewConversation() {
    setConversationId(null);
    setMessages([]);
    setQuestion("");
    setError("");
    setActiveCitation(null);
    sourceRefs.current = {};

    if (highlightTimer.current) {
      window.clearTimeout(highlightTimer.current);
      highlightTimer.current = null;
    }
  }

  // Scroll to the source associated with a clicked citation.
  function handleCitationClick(messageId, citationId) {
    const sourceKey = `${messageId}-${citationId}`;
    const sourceElement = sourceRefs.current[sourceKey];

    if (!sourceElement) {
      return;
    }

    if (highlightTimer.current) {
      window.clearTimeout(highlightTimer.current);
    }

    setActiveCitation(sourceKey);

    sourceElement.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });

    highlightTimer.current = window.setTimeout(() => {
      setActiveCitation((current) =>
        current === sourceKey ? null : current
      );

      highlightTimer.current = null;
    }, 2200);
  }

  async function handleSubmit(event) {
    event.preventDefault();

    const trimmedQuestion = question.trim();

    if (
      !trimmedQuestion ||
      loading ||
      !document?.document_id
    ) {
      return;
    }

    const userMessage = {
      message_id: `temporary-${Date.now()}`,
      role: "user",
      content: trimmedQuestion,
      sources: [],
    };

    setMessages((previous) => [...previous, userMessage]);
    setQuestion("");
    setLoading(true);
    setError("");

    try {
      const response = await askQuestion({
        documentId: document.document_id,
        question: trimmedQuestion,
        conversationId,
      });

      setConversationId(response.conversation_id);

      setMessages((previous) => [
        ...previous,
        {
          message_id: `answer-${Date.now()}`,
          role: "assistant",
          content: response.answer,
          sources: response.sources || [],
        },
      ]);

      await loadConversations(document.document_id);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Could not generate an answer. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  // Convert valid citation markers into internal Markdown links.
  // ReactMarkdown renders those links as buttons.
  function renderAnswer(text, messageId, sources = []) {
    const sourceIds = new Set(
      sources.map((source) => Number(source.citation_id))
    );

    const preparedText = (text || "").replace(
      /\[(\d+)\](?!\()/g,
      (match, number) => {
        const citationId = Number(number);

        if (!sourceIds.has(citationId)) {
          return match;
        }

        return `[${citationId}](#documind-source-${messageId}-${citationId})`;
      }
    );

    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children, ...props }) => {
            if (href?.startsWith("#documind-source-")) {
              const match = href.match(/-(\d+)$/);
              const citationId = match
                ? Number(match[1])
                : null;

              return (
                <button
                  type="button"
                  className="citation-link"
                  onClick={() => {
                    if (citationId !== null) {
                      handleCitationClick(
                        messageId,
                        citationId
                      );
                    }
                  }}
                  aria-label={`View source ${citationId}`}
                  title={`Go to source ${citationId}`}
                >
                  {children}
                </button>
              );
            }

            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                {...props}
              >
                {children}
              </a>
            );
          },

          table: ({ children, ...props }) => (
            <div className="markdown-table-wrapper">
              <table {...props}>{children}</table>
            </div>
          ),
        }}
      >
        {preparedText}
      </ReactMarkdown>
    );
  }

  if (!document) {
    return (
      <section className="chat-empty">
        <div className="chat-empty-icon">
          <BookOpen size={30} />
        </div>

        <h2>Select a document</h2>

        <p>
          Choose a PDF from the library to start asking questions.
        </p>
      </section>
    );
  }

  return (
    <section className="chat-workspace">
      <header className="chat-header">
        <div className="chat-document-info">
          <div className="chat-document-icon">
            <BookOpen size={20} />
          </div>

          <div>
            <h2>{document.filename}</h2>
            <p>
              {document.page_count} pages · Ask questions about this PDF
            </p>
          </div>
        </div>

        <button
          type="button"
          className="new-chat-button"
          onClick={startNewConversation}
          disabled={loading}
        >
          <Plus size={17} />
          New chat
        </button>
      </header>

      <div className="chat-history-bar">
        <label htmlFor="conversation-select">
          <MessageSquare size={16} />
          Previous conversations
        </label>

        <select
          id="conversation-select"
          value={conversationId || ""}
          onChange={(event) => {
            if (event.target.value) {
              openConversation(event.target.value);
            } else {
              startNewConversation();
            }
          }}
          disabled={historyLoading || loading}
        >
          <option value="">New conversation</option>

          {conversations.map((conversation) => (
            <option
              key={conversation.conversation_id}
              value={conversation.conversation_id}
            >
              {conversation.title}
            </option>
          ))}
        </select>
      </div>

      <div className="chat-messages">
        {historyLoading && (
          <div className="chat-loading">
            <LoaderCircle className="spin" size={18} />
            Loading conversation...
          </div>
        )}

        {!historyLoading && messages.length === 0 && (
          <div className="chat-welcome">
            <div className="chat-welcome-icon">
              <Bot size={30} />
            </div>

            <h3>Ask your document anything</h3>

            <p>
              Ask about concepts, summaries, methodologies, skills,
              or other information contained in this PDF.
            </p>
          </div>
        )}

        {messages.map((message) => {
          const messageId = message.message_id;
          const messageSources = message.sources || [];

          return (
            <article
              className={`chat-message ${message.role}`}
              key={messageId}
            >
              <div className="message-avatar">
                {message.role === "user" ? (
                  <UserRound size={18} />
                ) : (
                  <Bot size={18} />
                )}
              </div>

              <div className="message-content">
                <div className="message-role">
                  {message.role === "user" ? "You" : "DocuMind"}
                </div>

                <div
                  className={
                    message.role === "assistant"
                      ? "message-text markdown-content"
                      : "message-text"
                  }
                >
                  {message.role === "assistant"
                    ? renderAnswer(
                        message.content,
                        messageId,
                        messageSources
                      )
                    : message.content}
                </div>

                {message.role === "assistant" &&
                  messageSources.length > 0 && (
                    <div className="source-list">
                      <div className="source-heading">
                        <BookOpen size={15} />
                        Sources
                      </div>

                      {messageSources.map((source, index) => {
                        const citationId = Number(
                          source.citation_id
                        );

                        const sourceKey =
                          `${messageId}-${citationId}`;

                        return (
                          <div
                            className={`source-item ${
                              activeCitation === sourceKey
                                ? "source-highlight"
                                : ""
                            }`}
                            key={`${citationId}-${source.chunk_index ?? index}`}
                            id={`source-${messageId}-${citationId}`}
                            ref={(element) => {
                              if (element) {
                                sourceRefs.current[sourceKey] =
                                  element;
                              } else {
                                delete sourceRefs.current[sourceKey];
                              }
                            }}
                          >
                            <span className="source-number">
                              [{citationId}]
                            </span>

                            <div className="source-details">
                              <span className="source-filename">
                                {source.filename}
                              </span>

                              <span className="source-page">
                                Page {source.page_number}
                                {source.chunk_index !== undefined &&
                                  ` · Chunk ${source.chunk_index}`}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
              </div>
            </article>
          );
        })}

        {loading && (
          <div className="chat-loading">
            <LoaderCircle className="spin" size={18} />
            Searching your document and generating an answer...
          </div>
        )}

        {error && (
          <div className="chat-error" role="alert">
            <AlertCircle size={17} />
            {error}
          </div>
        )}
      </div>

      <form className="chat-composer" onSubmit={handleSubmit}>
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask a question about this PDF..."
          rows={2}
          maxLength={2000}
          disabled={loading}
          onKeyDown={(event) => {
            if (
              event.key === "Enter" &&
              !event.shiftKey &&
              !event.nativeEvent.isComposing
            ) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
        />

        <div className="composer-footer">
          <span>
            Answers are generated from retrieved PDF passages.
          </span>

          <button
            type="submit"
            className="send-button"
            disabled={loading || !question.trim()}
            aria-label="Send question"
          >
            {loading ? (
              <LoaderCircle className="spin" size={18} />
            ) : (
              <ArrowUp size={19} />
            )}
          </button>
        </div>
      </form>
    </section>
  );
}

export default ChatWindow;
