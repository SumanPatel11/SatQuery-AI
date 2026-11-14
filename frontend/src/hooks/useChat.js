import { useCallback, useState } from "react";

function useChat() {
  const [messages, setMessages] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);

  const addMessage = useCallback((message) => {
    if (!message?.content?.trim()) {
      return;
    }

    setMessages((currentMessages) => [
      ...currentMessages,
      {
        id: message.id ?? `${Date.now()}-${currentMessages.length}`,
        role: message.role ?? "user",
        content: message.content.trim(),
        timestamp:
          message.timestamp ?? new Date().toISOString(),
        ...message,
      },
    ]);
  }, []);

  const sendMessage = useCallback(
    async (content) => {
      if (!content?.trim() || isProcessing) {
        return false;
      }

      const query = content.trim();

      setError(null);
      setIsProcessing(true);

      addMessage({
        role: "user",
        content: query,
      });

      /*
       * NLP/backend integration will be connected here.
       * No fabricated AI response is generated.
       */

      return true;
    },
    [addMessage, isProcessing]
  );

  const addAssistantMessage = useCallback(
    (content, metadata = {}) => {
      if (!content?.trim()) {
        return;
      }

      addMessage({
        role: "assistant",
        content,
        ...metadata,
      });
    },
    [addMessage]
  );

  const setProcessing = useCallback((value) => {
    setIsProcessing(Boolean(value));
  }, []);

  const setChatError = useCallback((message) => {
    setError(message || null);
    setIsProcessing(false);
  }, []);

  const clearChat = useCallback(() => {
    setMessages([]);
    setError(null);
    setIsProcessing(false);
  }, []);

  return {
    messages,
    isProcessing,
    error,

    addMessage,
    sendMessage,
    addAssistantMessage,
    setProcessing,
    setChatError,
    clearChat,
  };
}

export default useChat;