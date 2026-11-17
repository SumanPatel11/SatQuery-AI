import { useCallback, useLayoutEffect, useRef, useState } from "react";
import { useSessionContext } from "../context/SessionContext";

function useChat({ onAnalyze } = {}) {
  const {
    sessionId,
    conversationMessages: messages,
    appendConversationMessage,
    resetConversation,
    addQueryToHistory,
  } = useSessionContext();
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  const processingRef = useRef(false);
  const currentSessionRef = useRef(sessionId);
  useLayoutEffect(() => {
    currentSessionRef.current = sessionId;
  }, [sessionId]);

  const addMessage = useCallback((message) => {
    if (!message?.content?.trim()) {
      return;
    }

    appendConversationMessage({
      id: message.id ?? `${Date.now()}-${messages.length}`,
      role: message.role ?? "user",
      content: message.content.trim(),
      timestamp: message.timestamp ?? new Date().toISOString(),
      ...message,
    });
  }, [appendConversationMessage, messages.length]);

  const sendMessage = useCallback(
    async (content) => {
      if (!content?.trim() || processingRef.current) {
        return false;
      }

      const query = content.trim();
      const submittedSessionId = sessionId;

      processingRef.current = true;
      setError(null);
      setIsProcessing(true);

      addMessage({
        role: "user",
        content: query,
      });
      addQueryToHistory(query);
      try {
        if (!onAnalyze) {
          setError("Analysis is unavailable because no analysis handler is connected.");
          return false;
        }

        const response = await onAnalyze(query);
        if (currentSessionRef.current !== submittedSessionId) {
          return false;
        }
        if (response?.status !== "success") {
          setError(
            response?.error ||
              "Analysis could not be completed. See the Analysis Console for details."
          );
          return false;
        }

        addMessage({
          role: "assistant",
          content: response.assistant_response
            || "The analysis completed, but the backend did not include a conversational response.",
          analysis: response,
          timestamp: new Date().toISOString(),
          status: "completed",
          analysisId: response.analysis_id,
        });
        return response;
      } catch (requestError) {
        setError(requestError?.message || "Analysis request failed.");
        return false;
      } finally {
        processingRef.current = false;
        setIsProcessing(false);
      }
    },
    [addMessage, addQueryToHistory, onAnalyze, sessionId]
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
    processingRef.current = Boolean(value);
    setIsProcessing(Boolean(value));
  }, []);

  const setChatError = useCallback((message) => {
    setError(message || null);
    processingRef.current = false;
    setIsProcessing(false);
  }, []);

  const clearChat = useCallback(() => {
    resetConversation();
    setError(null);
    if (!processingRef.current) setIsProcessing(false);
  }, [resetConversation]);

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
