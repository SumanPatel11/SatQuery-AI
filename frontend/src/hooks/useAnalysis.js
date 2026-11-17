import { useCallback, useLayoutEffect, useRef } from "react";
import { ANALYSIS_STATUS } from "../utils/constants";
import { useAppContext } from "../context/AppContext";
import { sendChatQuery } from "../services/chatApi";
import { getAnalysisErrorMessage } from "../utils/analysisSummary";
import { useSessionContext } from "../context/SessionContext";

const BUILDING_CHANGE_QUERY = /\b(change|changed|changes|difference|differences|compare|comparison|before|after|demolish(?:ed|ition)?|new(?:ly)?\s+built|construction|disappear(?:ed|s)?)\b/i;

function useAnalysis() {
  const { sessionId, createSession } = useSessionContext();
  const {
    analysisStatus,
    setAnalysisStatus,
    activeAnalysis,
    setActiveAnalysis,
    selectedImage,
    setSelectedImage,
    selectedSecondImage,
    error,
    setError,
    clearError,
  } = useAppContext();
  const latestImageRef = useRef(selectedImage);
  useLayoutEffect(() => {
    latestImageRef.current = selectedImage;
  }, [selectedImage]);
  const requestSequence = useRef(0);

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
        const message = "Upload a before image before starting analysis.";
        setError(message);
        return analysisRequest.returnFailureDetails
          ? { status: "blocked", error: message }
          : false;
      }

      if (
        selectedImage.uploadStatus !== "uploaded" ||
        !selectedImage.image_id
      ) {
        const message = "Wait for the before image upload to finish before starting analysis.";
        setError(message);
        return analysisRequest.returnFailureDetails
          ? { status: "blocked", error: message }
          : false;
      }

      const query = analysisRequest.query?.trim();

      if (!query) {
        const message = "Enter a query before starting analysis.";
        setError(message);
        return analysisRequest.returnFailureDetails
          ? { status: "blocked", error: message }
          : false;
      }

      const requiresPair = BUILDING_CHANGE_QUERY.test(query);
      if (requiresPair && selectedSecondImage?.uploadStatus === "uploading") {
        const message = "Wait for the after image upload to finish before running change analysis.";
        setError(message);
        return analysisRequest.returnFailureDetails
          ? { status: "blocked", error: message }
          : false;
      }
      if (
        requiresPair &&
        (selectedSecondImage?.uploadStatus !== "uploaded" || !selectedSecondImage?.image_id)
      ) {
        const message = "Building-change analysis requires an uploaded before image and an uploaded after image.";
        setError(message);
        return analysisRequest.returnFailureDetails
          ? { status: "blocked", error: message }
          : false;
      }

      clearError();
      setError(null);
      const requestId = ++requestSequence.current;
      const submittedImageId = selectedImage.image_id;
      setAnalysisStatus(ANALYSIS_STATUS.PROCESSING);

      setActiveAnalysis({
        query,
        imageName: selectedImage.name,
        startedAt: new Date().toISOString(),
      });

      try {
        const result = await sendChatQuery({
          imageId: selectedImage.image_id,
          secondImageId: selectedSecondImage?.image_id || null,
          query,
          sessionId,
        });

        if (
          requestId !== requestSequence.current
          || latestImageRef.current?.image_id !== submittedImageId
        ) {
          return { status: "stale" };
        }

        if (result?.session_id && result.session_id !== sessionId) {
          createSession(result.session_id);
        }

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

          const backendError = getAnalysisErrorMessage(result);

          setError(
            backendError ||
            (result.status === "blocked"
              ? "Analysis was blocked by backend capability validation."
              : "Backend analysis execution failed.")
          );

          return analysisRequest.returnFailureDetails
            ? {
                status: result.status,
                error: backendError || "Backend analysis execution failed.",
                response: result,
              }
            : false;
        }

        throw new Error(
          "Backend returned an unexpected analysis response."
        );
      } catch (analysisError) {
        if (
          requestId !== requestSequence.current
          || latestImageRef.current?.image_id !== submittedImageId
        ) {
          return { status: "stale" };
        }
        setAnalysisStatus(ANALYSIS_STATUS.ERROR);
        setError(
          analysisError.message || "Analysis request failed."
        );
        return analysisRequest.returnFailureDetails
          ? {
              status: "failed",
              error: analysisError.message || "Analysis request failed.",
            }
          : false;
      }
    },
    [
      selectedImage,
      selectedSecondImage,
      sessionId,
      createSession,
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

