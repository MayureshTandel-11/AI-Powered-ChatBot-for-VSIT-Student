function getInitials(name) {
  if (!name) return "?";
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export default function Sidebar({
  user,
  sessions,
  activeSessionId,
  showProfile,
  onNewChat,
  onSelectSession,
  onToggleProfile,
  onLogout,
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <span className="sidebar-brand-icon">🎓</span>
          <div>
            <h1>College AI Assistant</h1>
            <p>Student Chatbot</p>
          </div>
        </div>

        <div className="sidebar-user">
          <span className="user-avatar">{getInitials(user.name)}</span>
          <div>
            <p className="user-name">{user.name}</p>
            <p className="user-email">{user.email}</p>
          </div>
        </div>
      </div>

      <button type="button" className="sidebar-button primary" onClick={onNewChat}>
        + New Chat
      </button>

      <div className="sidebar-section">
        <h2>Recent Chats</h2>
        {sessions.length === 0 ? (
          <p className="sidebar-empty">No conversations yet. Start a new chat.</p>
        ) : (
          <ul className="session-list">
            {sessions.map((session) => (
              <li key={session.id}>
                <button
                  type="button"
                  className={`session-item ${activeSessionId === session.id ? "active" : ""}`}
                  onClick={() => onSelectSession(session.id)}
                >
                  <span className="session-title">{session.title}</span>
                  <span className="session-meta">{session.message_count} messages</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="sidebar-footer">
        <button type="button" className="sidebar-button" onClick={onToggleProfile}>
          Profile
        </button>
        <button type="button" className="sidebar-button danger" onClick={onLogout}>
          Logout
        </button>
      </div>

      {showProfile && (
        <div className="profile-panel">
          <h3>Profile Details</h3>
          <p>
            <strong>Name:</strong> {user.name}
          </p>
          <p>
            <strong>Email:</strong> {user.email}
          </p>
          <p>
            <strong>Role:</strong> {user.role}
          </p>
        </div>
      )}
    </aside>
  );
}
