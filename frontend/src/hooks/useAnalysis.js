import { useCallback } from "react";
import { ANALYSIS_STATUS } from "../utils/constants";
import { useAppContext } from "../context/AppContext";
import { analyzeImage } from "../services/analysisApi";

function useAnalysis() {
  const {
    analysisStatus,
    setAnalysisStatus,
    activeAnalysis,
    setActiveAnalysis,
    selectedImage,
    setSelectedImage,
    error,
    setError,
    clearError,
  } = useAppContext();

  const prepareAnalysis = useCallback(
    (image) => {
      if (!image) {
        setError("No image selected for analysis.");
        return false;
      }

      clearError();
      setSelectedImage(image);
      setActiveAnalysis(null);
      setAnalysisStatus(ANALYSIS_STATUS.IDLE);

      return true;
    },
    [
      clearError,
      setActiveAnalysis,
      setAnalysisStatus,
      setError,
      setSelectedImage,
    ]
  );

  const startAnalysis = useCallback(
    async (analysisRequest = {}) => {
      if (!selectedImage) {
        setError("Upload an image before starting analysis.");
        return false;
      }

      if (
        selectedImage.uploadStatus !== "uploaded" ||
        !selectedImage.image_id
      ) {
        setError("Please wait until image upload is complete.");
        return false;
      }

      const query = analysisRequest.query?.trim();

      if (!query) {
        setError("Enter a query before starting analysis.");
        return false;
      }

      clearError();
      setError(null);
      setAnalysisStatus(ANALYSIS_STATUS.PROCESSING);

      setActiveAnalysis({
        query,
        imageName: selectedImage.name,
        startedAt: new Date().toISOString(),
      });

      try {
        const result = await analyzeImage({
          image: selectedImage.image_id,
          query,
          analysisType: analysisRequest.analysisType ?? null,
          options: analysisRequest.options ?? {},
        });

        if (result?.status === "success") {
          setActiveAnalysis(result);
          setAnalysisStatus(ANALYSIS_STATUS.COMPLETED);
          clearError();
          return result;
        }

        if (
          result?.status === "blocked" ||
          result?.status === "failed"
        ) {
          setActiveAnalysis(result);
          setAnalysisStatus(ANALYSIS_STATUS.ERROR);

          const backendError =
            result?.execution?.results?.find(
              (item) => item.error
            )?.error;

          setError(
            backendError ||
            (result.status === "blocked"
              ? "Analysis was blocked by backend capability validation."
              : "Backend analysis execution failed.")
          );

          return false;
        }

        throw new Error(
          "Backend returned an unexpected analysis response."
        );
      } catch (analysisError) {
        setAnalysisStatus(ANALYSIS_STATUS.ERROR);
        setError(
          analysisError.message || "Analysis request failed."
        );
        return false;
      }
    },
    [
      selectedImage,
      clearError,
      setError,
      setAnalysisStatus,
      setActiveAnalysis,
    ]
  );

  const completeAnalysis = useCallback(
    (result) => {
      if (!result) {
        setError("Analysis returned no result.");
        setAnalysisStatus(ANALYSIS_STATUS.ERROR);
        return;
      }

      setActiveAnalysis(result);
      setAnalysisStatus(ANALYSIS_STATUS.COMPLETED);
      clearError();
    },
    [
      clearError,
      setActiveAnalysis,
      setAnalysisStatus,
      setError,
    ]
  );

  const failAnalysis = useCallback(
    (message) => {
      setAnalysisStatus(ANALYSIS_STATUS.ERROR);
      setError(message || "An error occurred during analysis.");
    },
    [setAnalysisStatus, setError]
  );

  const resetAnalysis = useCallback(() => {
    setAnalysisStatus(ANALYSIS_STATUS.IDLE);
    setActiveAnalysis(null);
    clearError();
  }, [
    clearError,
    setActiveAnalysis,
    setAnalysisStatus,
  ]);

  return {
    analysisStatus,
    activeAnalysis,
    selectedImage,
    error,
    prepareAnalysis,
    startAnalysis,
    completeAnalysis,
    failAnalysis,
    resetAnalysis,
  };
}

export default useAnalysis;

