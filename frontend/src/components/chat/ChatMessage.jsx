import {
  Bot,
  CheckCircle2,
  User,
} from "lucide-react";
import AnalysisSummary from "../analysis/AnalysisSummary";

function ChatMessage({
  role = "user",
  content,
  timestamp = null,
  status = null,
  analysis = null,
}) {
  const isUser = role === "user";

  return (
    <article
      className={`chat-message ${
        isUser
          ? "chat-message-user"
          : "chat-message-assistant"
      }`}
    >
      <div className="chat-message-avatar">
        {isUser ? (
          <User size={14} strokeWidth={1.7} />
        ) : (
          <Bot size={14} strokeWidth={1.7} />
        )}
      </div>

      <div className="chat-message-content">
        <div className="chat-message-meta">
          <span className="chat-message-role">
            {isUser ? "YOU" : "SATQUERY AI"}
          </span>

          {timestamp && (
            <time
              className="chat-message-time"
              dateTime={timestamp}
            >
              {new Date(timestamp).toLocaleTimeString(
                "en-IN",
                {
                  hour: "2-digit",
                  minute: "2-digit",
                }
              )}
            </time>
          )}
        </div>

        <div className="chat-message-bubble">
          {analysis ? <AnalysisSummary analysis={analysis} /> : <p>{content}</p>}
        </div>

        {status === "completed" && !isUser && (
          <div className="chat-message-status">
            <CheckCircle2
              size={11}
              strokeWidth={1.8}
            />
            <span>Analysis response generated</span>
          </div>
        )}
      </div>
    </article>
  );
}

export default ChatMessage;
