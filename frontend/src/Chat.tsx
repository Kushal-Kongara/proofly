import { KeyboardEvent, useRef, useState } from "react";
import { ApiError, ChatAnswerMode, ChatCitation, askChat } from "./api/chat";
import { ChatUiMessage, formatSourceLocation, toChatHistory } from "./lib/chat";
import "./Chat.css";

interface DisplayMessage extends ChatUiMessage {
  citations?: ChatCitation[];
  answerMode?: ChatAnswerMode;
}

const SUGGESTED_QUESTIONS = [
  "When does my current work authorization expire?",
  "What does my I-94 say about my admitted-until date?",
  "Does my judging invitation prove completed judging?",
  "Which document supports my current work authorization?",
];

const MODE_LABELS: Record<ChatAnswerMode, string> = {
  document_grounded: "Based on your documents",
  insufficient_document_evidence: "Not found in uploaded documents",
};

export default function Chat() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const send = async (questionText: string) => {
    const question = questionText.trim();
    if (!question || loading) return;

    const historyForRequest = toChatHistory(messages);
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setErrorMessage(null);
    setLoading(true);

    try {
      const response = await askChat(question, historyForRequest);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.answer,
          citations: response.citations,
          answerMode: response.answer_mode,
        },
      ]);
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Something went wrong asking Proofly.");
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send(input);
    }
  };

  const handleClear = () => {
    setMessages([]);
    setErrorMessage(null);
  };

  return (
    <section className="chat-page">
      <div className="chat-header">
        <div>
          <h2>Ask Proofly</h2>
          <p className="chat-subtitle">Answers are grounded only in your uploaded documents — not general immigration advice.</p>
        </div>
        {messages.length > 0 && (
          <button className="chat-clear-btn" onClick={handleClear} type="button" disabled={loading}>
            Clear chat
          </button>
        )}
      </div>

      <div className="chat-window">
        {messages.length === 0 && (
          <div className="chat-welcome">
            <p>
              Hi — I'm Proofly's document assistant. Ask me anything about your uploaded documents, and I'll answer only from
              what's actually in them, with sources you can check.
            </p>
            <div className="chat-suggestions">
              {SUGGESTED_QUESTIONS.map((question) => (
                <button
                  className="chat-suggestion-btn"
                  key={question}
                  type="button"
                  onClick={() => send(question)}
                  disabled={loading}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message, i) => (
          <div className={`chat-message chat-message--${message.role}`} key={i}>
            <span className="chat-message-role">{message.role === "user" ? "You" : "Proofly"}</span>
            <p className="chat-message-content">{message.content}</p>

            {message.role === "assistant" && message.answerMode && (
              <span className={`chat-mode-badge chat-mode-badge--${message.answerMode}`}>{MODE_LABELS[message.answerMode]}</span>
            )}

            {message.role === "assistant" && message.citations && message.citations.length > 0 && (
              <details className="chat-sources">
                <summary>Sources ({message.citations.length})</summary>
                <div className="chat-source-cards">
                  {message.citations.map((citation) => (
                    <div className="chat-source-card" key={citation.source_key}>
                      <span className="chat-source-filename">{formatSourceLocation(citation.filename, citation.page_number)}</span>
                      <p className="chat-source-excerpt">"{citation.excerpt}"</p>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        ))}

        {loading && <p className="chat-status chat-status--loading">Searching your documents…</p>}
        {errorMessage && <p className="chat-status chat-status--error">{errorMessage}</p>}
      </div>

      <div className="chat-input-row">
        <textarea
          ref={textareaRef}
          className="chat-input"
          placeholder="Ask about your uploaded documents…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          rows={2}
        />
        <button className="chat-send-btn" onClick={() => send(input)} disabled={loading || !input.trim()} type="button">
          {loading ? "Sending…" : "Send"}
        </button>
      </div>

      <p className="legal-disclaimer">Proofly organizes document-derived information and is not legal advice.</p>
    </section>
  );
}
