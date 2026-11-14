import { createContext, useContext, useMemo, useState } from "react";
import {
  ANALYSIS_STATUS,
  DEFAULT_VIEWER_LAYERS,
} from "../utils/constants";

const AppContext = createContext(null);

function AppProvider({ children }) {
  const [analysisStatus, setAnalysisStatus] = useState(
    ANALYSIS_STATUS.IDLE
  );

  const [viewerLayers, setViewerLayers] = useState(
    DEFAULT_VIEWER_LAYERS
  );

  const [activeAnalysis, setActiveAnalysis] = useState(null);

  const [selectedImage, setSelectedImage] = useState(null);

  const [error, setError] = useState(null);

  const toggleViewerLayer = (layerKey) => {
    setViewerLayers((currentLayers) => ({
      ...currentLayers,
      [layerKey]: !currentLayers[layerKey],
    }));
  };

  const resetViewerLayers = () => {
    setViewerLayers(DEFAULT_VIEWER_LAYERS);
  };

  const clearError = () => {
    setError(null);
  };

  const value = useMemo(
    () => ({
      analysisStatus,
      setAnalysisStatus,

      viewerLayers,
      setViewerLayers,
      toggleViewerLayer,
      resetViewerLayers,

      activeAnalysis,
      setActiveAnalysis,

      selectedImage,
      setSelectedImage,

      error,
      setError,
      clearError,
    }),
    [
      analysisStatus,
      viewerLayers,
      activeAnalysis,
      selectedImage,
      error,
    ]
  );

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
}

export function useAppContext() {
  const context = useContext(AppContext);

  if (!context) {
    throw new Error(
      "useAppContext must be used inside AppProvider."
    );
  }

  return context;
}

export default AppProvider;