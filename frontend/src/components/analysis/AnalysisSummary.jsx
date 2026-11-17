import { useState } from "react";
import { getAnalysisSummaryItems, getAssistantResponse, getVegetationPresentation } from "../../utils/analysisSummary";
import { getChangeOverlayUrl } from "../../services/api";

function count(value) {
  return Number.isInteger(value) && value >= 0 ? value.toLocaleString() : "—";
}

function percent(value) {
  return typeof value === "number" && Number.isFinite(value)
    ? `${(value * 100).toFixed(2)}%`
    : "—";
}

function ChangeOverlayPreview({ analysisId }) {
  const [unavailable, setUnavailable] = useState(false);
  const src = getChangeOverlayUrl(analysisId);

  if (!src || unavailable) return null;

  return (
    <figure className="analysis-change-preview">
      <img
        src={src}
        alt="Model change overlay for the after image"
        onError={() => setUnavailable(true)}
      />
      <figcaption>Model overlay for the after image; highlighted pixels indicate predicted change.</figcaption>
    </figure>
  );
}

function NlpInsights({ analysis }) {
  const insights = analysis?.nlp_insights || {};
  const m1 = insights.m1 || analysis?.nlp?.m1 || {};
  const predictions = m1.predictions || {};
  const m2 = insights.m2 || analysis?.nlp?.m2 || {};
  const tasks = insights.task_plan?.tasks || analysis?.nlp?.task_plan?.tasks || [];
  const routing = insights.routing || analysis?.nlp?.routing || {};
  const capabilities = insights.capability_validation
    || analysis?.nlp?.capability_validation || {};

  return (
    <details className="analysis-summary-details nlp-insights">
      <summary>NLP insights</summary>
      <div className="nlp-insights-body">
        <p><strong>Original query:</strong> {insights.original_query || analysis?.query || "—"}</p>
        <section>
          <h5>M1 · DistilBERT</h5>
          <p>Intent: {m1.intent || "not returned"}</p>
          {Object.keys(predictions).length > 0 && (
            <ul>
              {Object.entries(predictions).map(([head, item]) => (
                <li key={head}>
                  {head}: {item?.label || "not returned"}
                  {typeof item?.confidence === "number" ? ` (${(item.confidence * 100).toFixed(2)}%)` : ""}
                </li>
              ))}
            </ul>
          )}
          {Array.isArray(m1.tokenized_input) && m1.tokenized_input.length > 0 && (
            <p><strong>Tokens:</strong> <code>{m1.tokenized_input.join(" · ")}</code></p>
          )}
        </section>
        <section>
          <h5>M2 · Qwen3 interpretation</h5>
          <p>Model: {m2.model || "not reported"}; decomposition: {m2.combine || "not returned"}</p>
          {Array.isArray(m2.subqueries) && m2.subqueries.length > 0 && (
            <ul>{m2.subqueries.map((query, index) => <li key={`${index}-${query}`}>{query}</li>)}</ul>
          )}
        </section>
        <section>
          <h5>Planner and router</h5>
          <ul>
            {tasks.map((task, index) => (
              <li key={`${task.task || task.target}-${index}`}>
                Planned: {task.operation} {task.target}
              </li>
            ))}
            {(routing.tasks || []).map((task, index) => (
              <li key={`${task.task}-${index}`}>
                Capability: {task.task} · {task.status || "not returned"}
              </li>
            ))}
          </ul>
          <p>Planner capability validation: {capabilities.overall_status || "not returned"}</p>
        </section>
        {insights.context_resolution && (
          <p><strong>Context:</strong> {insights.context_resolution.status}</p>
        )}
        {insights.response_generation && (
          <p><strong>Response generation:</strong> {insights.response_generation.status} · {insights.response_generation.model}</p>
        )}
      </div>
    </details>
  );
}

function AnalysisSummary({ analysis }) {
  const execution = analysis?.execution || {};
  const results = getAnalysisSummaryItems(analysis);
  const validationReason = execution.validation?.reason;

  return (
    <div className="analysis-summary">
      <p className="analysis-summary-answer">
        {getAssistantResponse(analysis)}
      </p>
      {results.length > 0 && (
        <p className="analysis-summary-meta">
          {[...new Set(results.map((item) => [item.model, item.device].filter(Boolean).join(" · ")).filter(Boolean))].join("; ")}
        </p>
      )}

      {results.map((item, index) => {
        const task = item.task;
        const detections = item.detections;
        const classCounts = item.classPixelCounts;
        const vegetation = getVegetationPresentation(analysis, item);
        return (
          <section className="analysis-summary-result" key={`${task}-${index}`}>
            <details className="analysis-summary-details">
              <summary>{task.replaceAll("_", " ")} details</summary>
              {typeof item.buildingCount === "number" && (
                <p>{count(item.buildingCount)} building detections were returned.</p>
              )}
              {detections.length > 0 && (
                <ul>
                  {detections.map((detection, detectionIndex) => (
                    <li key={`${detection.class_id ?? "class"}-${detectionIndex}`}>
                      {detection.class_name || `Class ${detection.class_id ?? "—"}`}
                      {typeof detection.confidence === "number" ? ` · confidence ${detection.confidence.toFixed(4)}` : ""}
                      {Array.isArray(detection.bbox_xyxy) ? ` · box [${detection.bbox_xyxy.join(", ")}]` : ""}
                      {Array.isArray(detection.center) && detection.center.length === 2
                        ? ` · center (${detection.center.map((value) => Number.isFinite(value) ? value.toFixed(1) : "—").join(", ")}) px`
                        : ""}
                    </li>
                  ))}
                </ul>
              )}
              {classCounts && typeof classCounts === "object" && !vegetation && (
                <ul>{Object.entries(classCounts).map(([name, value]) => (
                  <li key={name}>{name}: {count(value)} pixels</li>
                ))}</ul>
              )}
              {vegetation && (
                <ul>
                  <li>Forest pixels: {count(vegetation.forestPixels)}</li>
                  <li>Agriculture pixels: {count(vegetation.agriculturePixels)}</li>
                  {vegetation.totalVegetationPixels !== undefined && <li>Total vegetation pixels: {count(vegetation.totalVegetationPixels)}</li>}
                  {typeof vegetation.vegetationPixelPercentage === "number" && Number.isFinite(vegetation.vegetationPixelPercentage) && <li>Vegetation image pixel percentage: {vegetation.vegetationPixelPercentage.toFixed(2)}%</li>}
                </ul>
              )}
              {typeof item.changedPixels === "number" && (
                <p>Changed pixels: {count(item.changedPixels)}{typeof item.changedFraction === "number" ? ` · ${percent(item.changedFraction)} pixel fraction` : ""}</p>
              )}
              {item.error && <p className="analysis-summary-error">{item.error}</p>}
            </details>
            {typeof item.changedPixels === "number" && (
              <ChangeOverlayPreview analysisId={analysis.analysis_id || analysis.run_id} />
            )}
            {typeof item.floodPixels === "number" && <p className="analysis-summary-result-note">Flood pixels: {count(item.floodPixels)} · valid: {count(item.validPixels)} · invalid: {count(item.invalidPixels)} · {percent(item.floodPixelFraction)} image-pixel fraction</p>}
          </section>
        );
      })}

      {results.length === 0 && (
        <p>{validationReason || "The backend returned no CV result records for this request."}</p>
      )}

      <NlpInsights analysis={analysis} />
      <details className="analysis-summary-details technical-response">
        <summary>Technical response</summary>
        <pre>{JSON.stringify(analysis, null, 2)}</pre>
      </details>
    </div>
  );
}

export default AnalysisSummary;
