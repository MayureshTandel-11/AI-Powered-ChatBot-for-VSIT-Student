import { useCallback, useEffect, useState } from "react";
import ChatWindow from "../components/ChatWindow.jsx";
import Sidebar from "../components/Sidebar.jsx";
import { getChatHistory, getChatSession, logout } from "../services/api.js";

export default function Chat({ user, onLogout }) {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [showProfile, setShowProfile] = useState(false);
  const [loadingSession, setLoadingSession] = useState(false);

  const loadHistory = useCallback(async () => {
    try {
      const data = await getChatHistory();
      setSessions(data.sessions);
    } catch {
      setSessions([]);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  async function handleSelectSession(sessionId) {
    setLoadingSession(true);
    setShowProfile(false);
    setActiveSessionId(sessionId);

    try {
      const data = await getChatSession(sessionId);
      setMessages(data.messages);
    } catch {
      setMessages([]);
    } finally {
      setLoadingSession(false);
    }
  }

  function handleNewChat() {
    setActiveSessionId(null);
    setMessages([]);
    setShowProfile(false);
  }

  function handleLogout() {
    logout();
    onLogout();
  }

  return (
    <div className="chat-layout">
      <Sidebar
        user={user}
        sessions={sessions}
        activeSessionId={activeSessionId}
        showProfile={showProfile}
        onNewChat={handleNewChat}
        onSelectSession={handleSelectSession}
        onToggleProfile={() => setShowProfile((value) => !value)}
        onLogout={handleLogout}
      />

      <main className="chat-main">
        {loadingSession ? (
          <div className="loading-screen chat-loading">
            <div className="loading-box">
              <span className="loading-spinner" aria-hidden="true" />
              <p>Loading conversation...</p>
            </div>
          </div>
        ) : (
          <ChatWindow
            sessionId={activeSessionId}
            messages={messages}
            onMessagesChange={setMessages}
            onSessionCreated={setActiveSessionId}
            onHistoryRefresh={loadHistory}
          />
        )}
      </main>
    </div>
  );
}
