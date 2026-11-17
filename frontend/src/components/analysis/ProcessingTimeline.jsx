import { CheckCircle2, Circle, CircleDashed } from "lucide-react";

function ProcessingTimeline({ status = "standby", analysis = null }) {
  const executionStatus = analysis?.execution?.execution_status;
  const state =
    status === "completed"
      ? "completed"
      : status === "processing"
        ? "processing"
        : status === "error"
          ? "error"
          : "ready";

  const label = {
    ready: "Ready for analysis",
    processing: "Analysis request in progress",
    completed: "Analysis request completed",
    error: "Analysis request did not complete",
  }[state];

  const Icon = state === "completed"
    ? CheckCircle2
    : state === "processing"
      ? CircleDashed
      : Circle;

  return (
    <div className="processing-timeline">
      <div className="timeline-heading">
        <div className="timeline-heading-main">
          <span>REQUEST STATUS</span>
        </div>
        <span className="timeline-state">{state.toUpperCase()}</span>
      </div>
      <div className="timeline-list">
        <div className="timeline-item">
          <div className="timeline-marker-wrapper">
            <div className={`timeline-marker ${state}`}>
              <Icon size={11} strokeWidth={2} />
            </div>
          </div>
          <div className="timeline-step-content">
            <div className="timeline-step-top">
              <span className="timeline-step-label">{label}</span>
              {executionStatus && (
                <span className={`timeline-step-state ${state}`}>
                  Backend: {executionStatus}
                </span>
              )}
            </div>
            <div className="timeline-step-description">
              {state === "processing"
                ? "The backend does not report per-stage progress."
                : "Status reflects the request result reported by the application."}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ProcessingTimeline;
