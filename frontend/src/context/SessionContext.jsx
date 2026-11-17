import {
  createContext,
  useContext,
  useMemo,
  useState,
} from "react";

const SessionContext = createContext(null);

function makeSessionId() {
  return globalThis.crypto?.randomUUID?.()
    ?? `satquery-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function readSessionId() {
  try {
    return sessionStorage.getItem("satquery-session-id") || makeSessionId();
  } catch {
    return makeSessionId();
  }
}

function SessionProvider({ children }) {
  const [sessionId, setSessionId] = useState(readSessionId);
  const [conversationMessages, setConversationMessages] = useState([]);

  const [user, setUser] = useState({
    name: "Suman",
    role: "Analyst",
  });

  const [currentWorkspace, setCurrentWorkspace] =
    useState("New Scan");

  const [newScanToken, setNewScanToken] = useState(0);

  const [queryHistory, setQueryHistory] = useState([]);

  const createSession = (id) => {
    const nextId = id || makeSessionId();
    setSessionId(nextId);
    try { sessionStorage.setItem("satquery-session-id", nextId); } catch { /* storage is optional */ }
  };

  const resetConversation = () => {
    const nextId = makeSessionId();
    setSessionId(nextId);
    setConversationMessages([]);
    try { sessionStorage.setItem("satquery-session-id", nextId); } catch { /* storage is optional */ }
  };

  const appendConversationMessage = (message) => {
    setConversationMessages((current) => [...current, message]);
  };

  const openNewScan = () => {
    setCurrentWorkspace("New Scan");
    setNewScanToken((current) => current + 1);
    resetConversation();
  };

  const endSession = () => {
    resetConversation();
    setQueryHistory([]);
  };

  const addQueryToHistory = (query) => {
    if (!query?.trim()) {
      return;
    }

    setQueryHistory((currentHistory) => [
      ...currentHistory,
      {
        id: `${Date.now()}-${currentHistory.length}`,
        query: query.trim(),
        createdAt: new Date().toISOString(),
      },
    ]);
  };

  const clearQueryHistory = () => {
    setQueryHistory([]);
  };

  const value = useMemo(
    () => ({
      sessionId,
      conversationMessages,
      user,
      setUser,

      currentWorkspace,
      setCurrentWorkspace,
      newScanToken,
      openNewScan,

      queryHistory,

      createSession,
      resetConversation,
      appendConversationMessage,
      endSession,

      addQueryToHistory,
      clearQueryHistory,
    }),
    [
      sessionId,
      conversationMessages,
      user,
      currentWorkspace,
      newScanToken,
      queryHistory,
    ]
  );

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSessionContext() {
  const context = useContext(SessionContext);

  if (!context) {
    throw new Error(
      "useSessionContext must be used inside SessionProvider."
    );
  }

  return context;
}

export default SessionProvider;
