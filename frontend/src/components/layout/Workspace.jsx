import SatelliteViewer from "../viewer/SatelliteViewer";
import AnalysisPanel from "../analysis/AnalysisPanel";
import QueryInput from "../chat/QueryInput";
import useAnalysis from "../../hooks/useAnalysis";
import { ANALYSIS_STATUS } from "../../utils/constants";

function Workspace() {
  const {
    analysisStatus,
    activeAnalysis,
    selectedImage,
    error,
    startAnalysis,
  } = useAnalysis();

  const panelStatus =
    analysisStatus === ANALYSIS_STATUS.IDLE
      ? "standby"
      : analysisStatus === ANALYSIS_STATUS.UPLOADING
        ? "processing"
        : analysisStatus === ANALYSIS_STATUS.PROCESSING
          ? "processing"
          : analysisStatus === ANALYSIS_STATUS.COMPLETED
            ? "completed"
            : analysisStatus === ANALYSIS_STATUS.ERROR
              ? "error"
              : "standby";

  const handleQuerySubmit = (query) => {
    return startAnalysis({ query });
  };

  const isImageReady =
    selectedImage?.uploadStatus === "uploaded" &&
    Boolean(selectedImage?.image_id);

  const isProcessing =
    analysisStatus === ANALYSIS_STATUS.PROCESSING;

  return (
    <section className="workspace">
      <div className="workspace-header">
        <div className="workspace-heading">
          <div className="workspace-eyebrow">
            <span className="eyebrow-line" />
            <span>MULTIMODAL REMOTE SENSING</span>
          </div>

          <h1>Satellite Intelligence Workspace</h1>

          <p>
            Analyze satellite imagery through natural-language queries.
          </p>
        </div>

        <div className="workspace-state">
          <span className="workspace-state-dot" />
          <span>READY FOR INPUT</span>
        </div>
      </div>

      <div className="workspace-grid">
        <div className="viewer-column">
          <SatelliteViewer />
        </div>

        <div className="analysis-column">
          <AnalysisPanel
            status={panelStatus}
            analysis={activeAnalysis}
          />

          {error && (
            <div className="chat-error" role="alert">
              {error}
            </div>
          )}
        </div>
      </div>

      <QueryInput
        onSubmit={handleQuerySubmit}
        disabled={!isImageReady || isProcessing}
      />
    </section>
  );
}

export default Workspace;
