import {
  Activity,
  BrainCircuit,
  CircleDashed,
  Layers3,
  ShieldCheck,
} from "lucide-react";
import ProcessingTimeline from "./ProcessingTimeline";

function AnalysisPanel({ status = "standby", analysis = null }) {
  const statusConfig = {
    standby: {
      label: "Standby",
      indicator: <CircleDashed size={13} strokeWidth={1.7} />,
    },
    processing: {
      label: "Processing",
      indicator: <CircleDashed size={13} strokeWidth={1.7} />,
    },
    completed: {
      label: "Complete",
      indicator: <ShieldCheck size={13} strokeWidth={1.7} />,
    },
    error: {
      label: "Error",
      indicator: <CircleDashed size={13} strokeWidth={1.7} />,
    },
  };

  const currentStatus =
    statusConfig[status] || statusConfig.standby;

  const isProcessing = status === "processing";
  const isCompleted = status === "completed";
  const isError = status === "error";

  const firstResult = analysis?.execution?.results?.[0];
  const cvResult = firstResult?.result;

  const detectedTask =
    firstResult?.task ||
    analysis?.nlp?.routing?.tasks?.[0]?.task ||
    "—";

  const intentConfidence =
    analysis?.nlp?.m1?.predictions?.intent?.confidence;

  const confidenceDisplay =
    typeof intentConfidence === "number"
      ? `${(intentConfidence * 100).toFixed(2)}%`
      : "—";

  const validation =
    analysis?.nlp?.capability_validation?.overall_status ||
    "Pending";

  const floodPixelFraction =
    cvResult?.flood_area_pixel_fraction;

  const floodAreaDisplay =
    typeof floodPixelFraction === "number"
      ? `${(floodPixelFraction * 100).toFixed(2)}%`
      : "—";

  return (
    <section className="analysis-panel">
      <div className="analysis-panel-header">
        <div>
          <span className="panel-kicker">AI ANALYSIS</span>
          <h2>Analysis Console</h2>
        </div>

        <div className={`analysis-status analysis-status-${status}`}>
          <span className="analysis-status-indicator">
            {currentStatus.indicator}
          </span>
          <span>{currentStatus.label}</span>
        </div>
      </div>

      {status === "standby" && (
        <div className="analysis-empty">
          <div className="analysis-icon">
            <BrainCircuit size={24} strokeWidth={1.45} />
          </div>
          <span className="analysis-empty-kicker">
            MULTIMODAL ANALYSIS
          </span>
          <h3>Awaiting analysis</h3>
          <p>
            Upload an image and submit a natural-language query
            to start the SatQuery AI pipeline.
          </p>
        </div>
      )}

      {isProcessing && (
        <div className="analysis-empty">
          <div className="analysis-icon">
            <Activity size={24} strokeWidth={1.45} />
          </div>
          <span className="analysis-empty-kicker">
            MULTIMODAL ANALYSIS
          </span>
          <h3>Processing analysis</h3>
          <p>
            The SatQuery AI pipeline is processing the submitted
            image and query.
          </p>
        </div>
      )}

      {isCompleted && (
        <div className="analysis-empty">
          <div className="analysis-icon">
            <ShieldCheck size={24} strokeWidth={1.45} />
          </div>
          <span className="analysis-empty-kicker">
            ANALYSIS COMPLETE
          </span>
          <h3>Results available</h3>
          <p>
            {analysis?.query || "Analysis"} — backend execution:
            {" "}
            {analysis?.execution?.execution_status || "Completed"}.
          </p>
        </div>
      )}

      {isError && (
        <div className="analysis-empty">
          <div className="analysis-icon">
            <CircleDashed size={24} strokeWidth={1.45} />
          </div>
          <span className="analysis-empty-kicker">
            ANALYSIS ERROR
          </span>
          <h3>Analysis unavailable</h3>
          <p>
            {analysis?.execution?.results?.find(
              (item) => item.error
            )?.error ||
              "The analysis could not be completed. Check the analysis request and try again."}
          </p>
        </div>
      )}

      <div className="analysis-info-grid">
        <div className="analysis-info-card">
          <div className="analysis-info-icon">
            <Layers3 size={15} strokeWidth={1.6} />
          </div>
          <div className="analysis-info-content">
            <span>Detected task</span>
            <strong>{detectedTask}</strong>
          </div>
        </div>

        <div className="analysis-info-card">
          <div className="analysis-info-icon">
            <Activity size={15} strokeWidth={1.6} />
          </div>
          <div className="analysis-info-content">
            <span>Intent confidence</span>
            <strong>{confidenceDisplay}</strong>
          </div>
        </div>

        <div className="analysis-info-card">
          <div className="analysis-info-icon">
            <ShieldCheck size={15} strokeWidth={1.6} />
          </div>
          <div className="analysis-info-content">
            <span>Capability validation</span>
            <strong>{validation}</strong>
          </div>
        </div>
      </div>

      {isCompleted && (
        <div className="analysis-info-grid">
          <div className="analysis-info-card">
            <div className="analysis-info-icon">
              <Activity size={15} strokeWidth={1.6} />
            </div>
            <div className="analysis-info-content">
              <span>Flood pixel fraction</span>
              <strong>{floodAreaDisplay}</strong>
            </div>
          </div>

          <div className="analysis-info-card">
            <div className="analysis-info-icon">
              <BrainCircuit size={15} strokeWidth={1.6} />
            </div>
            <div className="analysis-info-content">
              <span>CV model</span>
              <strong>{cvResult?.model || "—"}</strong>
            </div>
          </div>

          <div className="analysis-info-card">
            <div className="analysis-info-icon">
              <ShieldCheck size={15} strokeWidth={1.6} />
            </div>
            <div className="analysis-info-content">
              <span>CV execution</span>
              <strong>
                {firstResult?.execution_status || "—"}
              </strong>
            </div>
          </div>
        </div>
      )}

      <ProcessingTimeline status={status} />
    </section>
  );
}

export default AnalysisPanel;

