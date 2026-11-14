import {
  BrainCircuit,
  CheckCircle2,
  Circle,
  ScanLine,
  Sparkles,
} from "lucide-react";

const pipelineSteps = [
  {
    key: "input",
    label: "Input validation",
    description: "Image and query validation",
    icon: CheckCircle2,
  },
  {
    key: "nlp",
    label: "NLP understanding",
    description: "Query understanding and intent extraction",
    icon: BrainCircuit,
  },
  {
    key: "planning",
    label: "Task planning",
    description: "Selecting the required analysis workflow",
    icon: Sparkles,
  },
  {
    key: "vision",
    label: "Vision analysis",
    description: "Running the selected computer vision task",
    icon: ScanLine,
  },
];

function getStepState(stepIndex, status) {
  if (status === "standby") {
    return stepIndex === 0 ? "ready" : "pending";
  }

  if (status === "processing") {
    if (stepIndex === 0) {
      return "completed";
    }

    if (stepIndex === 1) {
      return "processing";
    }

    return "pending";
  }

  if (status === "completed") {
    return "completed";
  }

  if (status === "error") {
    if (stepIndex === 0) {
      return "completed";
    }

    if (stepIndex === 1) {
      return "error";
    }

    return "pending";
  }

  return "pending";
}

function ProcessingTimeline({ status = "standby" }) {
  const timelineStatus =
    status === "completed"
      ? "COMPLETE"
      : status === "processing"
        ? "PROCESSING"
        : status === "error"
          ? "ERROR"
          : "STANDBY";

  return (
    <div className="processing-timeline">
      <div className="timeline-heading">
        <div className="timeline-heading-main">
          <span>PROCESSING PIPELINE</span>
        </div>

        <span className="timeline-state">
          {timelineStatus}
        </span>
      </div>

      <div className="timeline-list">
        {pipelineSteps.map((step, index) => {
          const Icon = step.icon;
          const stepState = getStepState(index, status);

          const isReady =
            stepState === "ready";

          const isCompleted =
            stepState === "completed";

          const isProcessing =
            stepState === "processing";

          const isError =
            stepState === "error";

          return (
            <div
              className="timeline-item"
              key={step.key}
            >
              <div className="timeline-marker-wrapper">
                <div
                  className={`timeline-marker ${stepState}`}
                >
                  {isReady || isCompleted ? (
                    <Icon
                      size={11}
                      strokeWidth={2}
                    />
                  ) : isProcessing ? (
                    <Circle
                      size={7}
                      fill="currentColor"
                      strokeWidth={0}
                    />
                  ) : isError ? (
                    <Circle
                      size={7}
                      fill="currentColor"
                      strokeWidth={0}
                    />
                  ) : (
                    <Circle
                      size={6}
                      fill="currentColor"
                      strokeWidth={0}
                    />
                  )}
                </div>

                {index < pipelineSteps.length - 1 && (
                  <div
                    className={`timeline-connector ${stepState}`}
                  />
                )}
              </div>

              <div className="timeline-step-content">
                <div className="timeline-step-top">
                  <span className="timeline-step-label">
                    {step.label}
                  </span>

                  <span
                    className={`timeline-step-state ${stepState}`}
                  >
                    {isReady && "READY"}
                    {isCompleted && "COMPLETE"}
                    {isProcessing && "PROCESSING"}
                    {isError && "ERROR"}
                    {stepState === "pending" && "PENDING"}
                  </span>
                </div>

                <div className="timeline-step-description">
                  {step.description}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default ProcessingTimeline;