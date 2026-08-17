import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { ApiError, ChatAnswerMode, ChatCitation, askChat } from "./api/chat";
import { ChatUiMessage, formatSourceLocation, toChatHistory } from "./lib/chat";
import "./Chat.css";

interface DisplayMessage extends ChatUiMessage {
  citations?: ChatCitation[];
  answerMode?: ChatAnswerMode;
}

const FEATURED_SUGGESTIONS = [
  {
    icon: "⏱️",
    title: "OPT Expiration Countdown",
    question: "When does my current Post-Completion OPT work authorization expire?",
    tag: "Timeline",
  },
  {
    icon: "🎓",
    title: "I-94 Admit-Until Date",
    question: "What does my official I-94 say about my admit-until status date?",
    tag: "Immigration Status",
  },
  {
    icon: "🏆",
    title: "O-1A Judging Criteria",
    question: "Does my peer review judging invitation support the O-1 Extraordinary Ability criteria?",
    tag: "O-1 Evidence",
  },
  {
    icon: "⚡",
    title: "STEM OPT Eligibility",
    question: "Which uploaded document supports my eligibility for a 24-month STEM OPT extension?",
    tag: "STEM Extension",
  },
];

const MODE_LABELS: Record<ChatAnswerMode, string> = {
  document_grounded: "Grounded in uploaded documents",
  insufficient_document_evidence: "Not found in uploaded documents",
};

export default function Chat() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

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
      {/* Top Chat Header Bar */}
      <div className="chat-header">
        <div>
          <div className="chat-title-row">
            <h2>Ask Proofly AI</h2>
            <span className="chat-status-pill">
              <span className="chat-status-dot" />
              Document-Grounded Zero-Hallucination
            </span>
          </div>
          <p className="chat-subtitle">
            Answers are computed strictly from your uploaded passport, visas, I-20s, I-94s, and EAD cards with exact page citations.
          </p>
        </div>

        {messages.length > 0 && (
          <button className="chat-clear-btn" onClick={handleClear} type="button" disabled={loading}>
            Clear Conversation
          </button>
        )}
      </div>

      {/* Main Chat Container */}
      <div className="chat-window">
        {messages.length === 0 ? (
          <div className="chat-welcome">
            <div className="chat-welcome-hero">
              <div className="chat-ai-avatar">✨</div>
              <div>
                <h3>How can I assist your immigration application today?</h3>
                <p>
                  I read your real vector-indexed documents in Supermemory to give grounded, citation-verified answers about your OPT timeline, status rules, and O-1A evidence.
                </p>
              </div>
            </div>

            <div className="chat-suggestions-grid">
              {FEATURED_SUGGESTIONS.map((s, idx) => (
                <button
                  key={`sug-${idx}`}
                  type="button"
                  className="chat-suggestion-card"
                  onClick={() => send(s.question)}
                  disabled={loading}
                >
                  <div className="chat-suggestion-top">
                    <span className="chat-suggestion-icon">{s.icon}</span>
                    <span className="chat-suggestion-tag">{s.tag}</span>
                  </div>
                  <h4 className="chat-suggestion-title">{s.title}</h4>
                  <p className="chat-suggestion-text">"{s.question}"</p>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="chat-messages-container">
            {messages.map((message, i) => (
              <div className={`chat-message-wrap chat-message-wrap--${message.role}`} key={i}>
                <div className="chat-avatar">
                  {message.role === "user" ? "👤" : "⚡"}
                </div>

                <div className={`chat-bubble chat-bubble--${message.role}`}>
                  <div className="chat-bubble-header">
                    <span className="chat-sender-name">
                      {message.role === "user" ? "You" : "Proofly Assistant"}
                    </span>
                    {message.role === "assistant" && message.answerMode && (
                      <span className={`chat-mode-badge chat-mode-badge--${message.answerMode}`}>
                        {MODE_LABELS[message.answerMode]}
                      </span>
                    )}
                  </div>

                  <p className="chat-bubble-content">{message.content}</p>

                  {message.role === "assistant" && message.citations && message.citations.length > 0 && (
                    <div className="chat-sources-block">
                      <span className="chat-sources-title">
                        Verified Sources ({message.citations.length})
                      </span>
                      <div className="chat-source-cards">
                        {message.citations.map((citation) => (
                          <div className="chat-source-card" key={citation.source_key}>
                            <span className="chat-source-filename">
                              📄 {formatSourceLocation(citation.filename, citation.page_number)}
                            </span>
                            {citation.excerpt && (
                              <p className="chat-source-excerpt">"{citation.excerpt}"</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {loading && (
          <div className="chat-message-wrap chat-message-wrap--assistant">
            <div className="chat-avatar">⚡</div>
            <div className="chat-bubble chat-bubble--assistant chat-loading-bubble">
              <span className="chat-typing-dots">
                <span>.</span><span>.</span><span>.</span>
              </span>
              <span style={{ fontSize: "0.88rem", fontWeight: 700, color: "#1e50e6" }}>
                Searching vector index in Supermemory…
              </span>
            </div>
          </div>
        )}

        {errorMessage && (
          <div className="chat-status chat-status--error">{errorMessage}</div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="chat-input-container">
        <textarea
          ref={textareaRef}
          className="chat-input"
          placeholder="Ask a question about your uploaded documents (e.g. 'When does my OPT expire?')..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          rows={2}
        />

        <button
          className="chat-send-btn"
          onClick={() => send(input)}
          disabled={loading || !input.trim()}
          type="button"
        >
          <span>Send</span>
          <span>➔</span>
        </button>
      </div>

      <p className="legal-disclaimer">
        Proofly organizes document-derived information for applicant convenience and is not a substitute for formal legal representation.
      </p>
    </section>
  );
}
