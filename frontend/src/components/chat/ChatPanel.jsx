import { Bot, MessageSquareText, RotateCcw } from "lucide-react";
import ChatMessage from "./ChatMessage";
import QuerySuggestions from "./QuerySuggestions";
import QueryInput from "./QueryInput";
import useChat from "../../hooks/useChat";

function ChatPanel() {
  const {
    messages,
    isProcessing,
    error,
    sendMessage,
    clearChat,
  } = useChat();

  const handleSuggestionSelect = (query) => {
    sendMessage(query);
  };

  return (
    <section className="chat-panel">
      <div className="chat-panel-header">
        <div className="chat-panel-heading">
          <div className="chat-panel-icon">
            <Bot size={16} strokeWidth={1.7} />
          </div>

          <div>
            <span className="chat-panel-kicker">
              AI ASSISTANT
            </span>

            <h2>Ask SatQuery</h2>
          </div>
        </div>

        <button
          type="button"
          className="chat-panel-reset"
          onClick={clearChat}
          disabled={messages.length === 0}
          aria-label="Clear conversation"
          title="Clear conversation"
        >
          <RotateCcw size={14} strokeWidth={1.7} />
        </button>
      </div>

      <div className="chat-panel-body">
        {messages.length === 0 ? (
          <div className="chat-empty-state">
            <div className="chat-empty-icon">
              <MessageSquareText
                size={22}
                strokeWidth={1.5}
              />
            </div>

            <div className="chat-empty-content">
              <span className="chat-empty-kicker">
                MULTIMODAL QUERY
              </span>

              <h3>
                Ask about your satellite image
              </h3>

              <p>
                Describe what you want to analyze using
                natural language.
              </p>
            </div>

            <QuerySuggestions
              onSelect={handleSuggestionSelect}
              disabled={isProcessing}
            />
          </div>
        ) : (
          <div className="chat-message-list">
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                role={message.role}
                content={message.content}
                timestamp={message.timestamp}
                status={message.status}
              />
            ))}

            {isProcessing && (
              <div className="chat-processing">
                <span className="chat-processing-dot" />
                <span className="chat-processing-dot" />
                <span className="chat-processing-dot" />
                <span className="chat-processing-text">
                  Processing query...
                </span>
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="chat-error">
            {error}
          </div>
        )}
      </div>

      <div className="chat-panel-input">
        <QueryInput
          onSubmit={sendMessage}
          disabled={isProcessing}
        />
      </div>
    </section>
  );
}

export default ChatPanel;