import { useEffect, useRef, useState } from "react";
import Message from "./Message.jsx";
import { sendChatMessage } from "../services/api.js";

const SUGGESTIONS = [
  "What is the minimum attendance requirement?",
  "When does the library open?",
  "When are semester examinations conducted?",
];

export default function ChatWindow({
  sessionId,
  messages,
  onMessagesChange,
  onSessionCreated,
  onHistoryRefresh,
}) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || loading) {
      return;
    }

    await sendQuestion(trimmed);
  }

  async function sendQuestion(trimmed) {
    setError("");
    setLoading(true);
    setInput("");

    const userMessage = {
      id: `temp-user-${Date.now()}`,
      role: "user",
      message: trimmed,
      created_at: new Date().toISOString(),
    };
    onMessagesChange((prev) => [...prev, userMessage]);

    try {
      const response = await sendChatMessage(trimmed, sessionId);
      if (!sessionId) {
        onSessionCreated(response.session_id);
      }

      const assistantMessage = {
        id: response.message_id,
        role: "assistant",
        message: response.answer,
        intent: response.intent,
        sources: response.sources,
        created_at: new Date().toISOString(),
      };

      onMessagesChange((prev) => [...prev, assistantMessage]);
      onHistoryRefresh();
    } catch (err) {
      setError(err.message);
      onMessagesChange((prev) => prev.filter((message) => message.id !== userMessage.id));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat-window">
      <header className="chat-header">
        <div>
          <h2>College Assistant</h2>
          <p>Ask questions about attendance, exams, library, fees, and more</p>
        </div>
      </header>

      <div className="chat-messages">
        {messages.length === 0 && !loading && (
          <div className="chat-empty">
            <div className="chat-empty-icon">💬</div>
            <h2>How can I help you today?</h2>
            <p>Choose a suggestion or type your own college-related question.</p>
            <div className="chat-suggestions">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  className="suggestion-chip"
                  onClick={() => sendQuestion(suggestion)}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => (
          <Message
            key={message.id}
            role={message.role}
            content={message.message}
            intent={message.intent}
            sources={message.sources}
          />
        ))}

        {loading && <Message role="assistant" content="" isLoading />}
        <div ref={messagesEndRef} />
      </div>

      {error && <div className="chat-error-banner">{error}</div>}

      <form className="chat-input-form" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask anything about your college..."
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          {loading ? "Sending..." : "Send"}
        </button>
      </form>
    </div>
  );
}
