import { useCallback } from "react";
import { useAppContext } from "../context/AppContext";
import { useSessionContext } from "../context/SessionContext";
import { ANALYSIS_STATUS } from "../utils/constants";

function useNewScan() {
  const { setActiveAnalysis, setAnalysisStatus, clearError } = useAppContext();
  const { openNewScan } = useSessionContext();

  return useCallback(() => {
    setActiveAnalysis(null);
    setAnalysisStatus(ANALYSIS_STATUS.IDLE);
    clearError();
    openNewScan();
  }, [clearError, openNewScan, setActiveAnalysis, setAnalysisStatus]);
}

export default useNewScan;
