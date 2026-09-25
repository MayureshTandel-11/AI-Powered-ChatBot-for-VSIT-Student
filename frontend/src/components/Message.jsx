function renderInlineMarkdown(text, keyPrefix) {
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_)/g);

  return tokens.map((token, index) => {
    const key = `${keyPrefix}-${index}`;
    if (!token) return null;
    if (token.startsWith("**") || token.startsWith("__")) {
      return <strong key={key}>{token.slice(2, -2)}</strong>;
    }
    if (token.startsWith("*") || token.startsWith("_")) {
      return <em key={key}>{token.slice(1, -1)}</em>;
    }
    if (token.startsWith("`") && token.endsWith("`")) {
      return <code key={key}>{token.slice(1, -1)}</code>;
    }
    return token;
  });
}

function renderMarkdown(content) {
  const lines = String(content ?? "").replace(/<br\s*\/?>/gi, "\n").split(/\r?\n/);
  const elements = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) {
      index += 1;
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      const Heading = `h${heading[1].length}`;
      elements.push(<Heading key={`heading-${index}`}>{renderInlineMarkdown(heading[2], `heading-${index}`)}</Heading>);
      index += 1;
      continue;
    }

    if (/^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line)) {
      elements.push(<hr key={`rule-${index}`} />);
      index += 1;
      continue;
    }

    const tableHeader = line.match(/^\|?\s*(.+?)\s*\|\s*$/);
    const nextLine = lines[index + 1]?.trim() ?? "";
    if (tableHeader && /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(nextLine)) {
      const headers = tableHeader[1].split("|").map((cell) => cell.trim());
      const rows = [];
      index += 2;
      while (index < lines.length && lines[index].includes("|")) {
        rows.push(lines[index].trim().replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim()));
        index += 1;
      }
      elements.push(
        <div className="message-table-wrap" key={`table-${index}`}>
          <table>
            <thead><tr>{headers.map((cell, cellIndex) => <th key={`th-${cellIndex}`}>{renderInlineMarkdown(cell, `th-${cellIndex}`)}</th>)}</tr></thead>
            <tbody>{rows.map((row, rowIndex) => <tr key={`tr-${rowIndex}`}>{headers.map((_, cellIndex) => <td key={`td-${rowIndex}-${cellIndex}`}>{renderInlineMarkdown(row[cellIndex] ?? "", `td-${rowIndex}-${cellIndex}`)}</td>)}</tr>)}</tbody>
          </table>
        </div>
      );
      continue;
    }

    const listMatch = line.match(/^([-*+] |\d+\. )(.+)$/);
    if (listMatch) {
      const ordered = /^\d/.test(listMatch[1]);
      const items = [];
      while (index < lines.length) {
        const item = lines[index].trim().match(ordered ? /^\d+\. (.+)$/ : /^[-*+] (.+)$/);
        if (!item) break;
        items.push(<li key={`item-${index}`}>{renderInlineMarkdown(item[1], `item-${index}`)}</li>);
        index += 1;
      }
      const List = ordered ? "ol" : "ul";
      elements.push(<List key={`list-${index}`}>{items}</List>);
      continue;
    }

    const paragraph = [line];
    index += 1;
    while (index < lines.length && lines[index].trim() && !/^(#{1,6})\s|^[-*+] |^\d+\. |^\|/.test(lines[index].trim())) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    elements.push(<p key={`paragraph-${index}`}>{paragraph.map((part, partIndex) => <span key={`part-${partIndex}`}>{partIndex > 0 && " "}{renderInlineMarkdown(part, `paragraph-${index}-${partIndex}`)}</span>)}</p>);
  }

  return elements;
}

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
            <div className="message-text message-markdown">{renderMarkdown(content)}</div>
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
