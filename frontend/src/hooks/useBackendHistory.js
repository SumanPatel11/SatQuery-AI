import { useCallback, useEffect, useState } from "react";
import { getAnalysisHistory } from "../services/analysisApi";

function useBackendHistory() {
  const [records, setRecords] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const requestRecords = useCallback(async () => {
    try {
      const response = await getAnalysisHistory();
      return { records: Array.isArray(response) ? response : [], error: null };
    } catch (requestError) {
      return {
        records: [],
        error: requestError?.message || "Unable to load analysis history.",
      };
    }
  }, []);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const result = await requestRecords();
    setRecords(result.records);
    setError(result.error);
    setIsLoading(false);
  }, [requestRecords]);

  useEffect(() => {
    let active = true;
    requestRecords().then((result) => {
      if (!active) return;
      setRecords(result.records);
      setError(result.error);
      setIsLoading(false);
    });
    return () => { active = false; };
  }, [requestRecords]);

  return { records, isLoading, error, refresh };
}

export default useBackendHistory;
