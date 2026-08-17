import { useState } from "react";
import Chat from "./Chat";
import "./ChatbotDrawer.css";

export default function ChatbotDrawer() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      {/* Floating Action Button */}
      <button
        type="button"
        className="chatbot-fab"
        onClick={() => setIsOpen(true)}
        aria-label="Ask Proofly AI Copilot"
      >
        <span className="chatbot-fab-icon">💬</span>
        <span>Ask Proofly</span>
      </button>

      {/* Side Drawer Modal */}
      {isOpen && (
        <div className="chatbot-drawer-overlay" onClick={() => setIsOpen(false)}>
          <div className="chatbot-drawer" onClick={(e) => e.stopPropagation()}>
            <header className="chatbot-drawer-header">
              <div className="chatbot-drawer-title-group">
                <div className="chatbot-drawer-badge">✨</div>
                <div>
                  <h2 className="chatbot-drawer-h2">Ask Proofly AI</h2>
                  <p className="chatbot-drawer-sub">Grounded strictly in your uploaded documents</p>
                </div>
              </div>

              <button
                type="button"
                className="chatbot-drawer-close"
                onClick={() => setIsOpen(false)}
                aria-label="Close chatbot drawer"
              >
                ✕
              </button>
            </header>

            <div className="chatbot-drawer-body">
              <Chat />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
