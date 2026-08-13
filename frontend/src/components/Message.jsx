export default function Message({ role, content, intent, sources = [], isLoading = false }) {
  const isUser = role === "user";

  return (
    <div className={`message-row ${isUser ? "message-row-user" : "message-row-assistant"}`}>
      {!isUser && (
        <span className="message-avatar assistant-avatar" aria-hidden="true">
          AI
        </span>
      )}

      <div className={`message-bubble ${isUser ? "message-user" : "message-assistant"}`}>
        {isLoading ? (
          <div className="typing-indicator">
            <span />
            <span />
            <span />
          </div>
        ) : (
          <>
            <p className="message-text">{content}</p>
            {!isUser && intent && (
              <p className="message-intent">
                Intent: <span>{intent}</span>
              </p>
            )}
            {!isUser && sources.length > 0 && (
              <div className="message-sources">
                <p className="sources-title">Sources</p>
                <ul>
                  {sources.map((source) => (
                    <li key={`${source.document}-${source.page ?? "na"}`}>
                      {source.document}
                      {source.page ? ` (page ${source.page})` : ""}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>

      {isUser && (
        <span className="message-avatar user-avatar" aria-hidden="true">
          You
        </span>
      )}
    </div>
  );
}
