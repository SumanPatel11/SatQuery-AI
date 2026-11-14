import {
  createContext,
  useContext,
  useMemo,
  useState,
} from "react";

const SessionContext = createContext(null);

function SessionProvider({ children }) {
  const [sessionId, setSessionId] = useState(null);

  const [user, setUser] = useState({
    name: "Suman",
    role: "Analyst",
  });

  const [currentWorkspace, setCurrentWorkspace] =
    useState("New Scan");

  const [queryHistory, setQueryHistory] = useState([]);

  const createSession = (id) => {
    setSessionId(id);
  };

  const endSession = () => {
    setSessionId(null);
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
      user,
      setUser,

      currentWorkspace,
      setCurrentWorkspace,

      queryHistory,

      createSession,
      endSession,

      addQueryToHistory,
      clearQueryHistory,
    }),
    [
      sessionId,
      user,
      currentWorkspace,
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