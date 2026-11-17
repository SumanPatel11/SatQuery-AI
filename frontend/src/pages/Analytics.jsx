import { useMemo } from "react";
import { BarChart3, CheckCircle2, Clock3, RefreshCw } from "lucide-react";
import useBackendHistory from "../hooks/useBackendHistory";
import useNewScan from "../hooks/useNewScan";

function Analytics() {
  const { records, isLoading, error, refresh } = useBackendHistory();
  const openNewScan = useNewScan();
  const stats = useMemo(() => ({
    success: records.filter((record) => record.status === "success").length,
    blocked: records.filter((record) => record.status === "blocked").length,
    failed: records.filter((record) => record.status === "failed").length,
  }), [records]);

  return (
    <section className="page-shell analytics-page">
      <div className="page-header">
        <div className="page-heading">
          <div className="page-eyebrow"><span className="page-eyebrow-line" /><span>ANALYTICS</span></div>
          <h1>Analysis Activity</h1>
          <p>Counts are calculated from records returned by the current backend session.</p>
        </div>
        <button type="button" className="record-action" onClick={refresh} disabled={isLoading}><RefreshCw size={14} /> Refresh</button>
      </div>

      {error && <p className="page-error" role="alert">{error}</p>}
      <div className="analytics-grid">
        <article className="analytics-card"><div className="analytics-card-icon"><BarChart3 size={18} /></div><div className="analytics-card-content"><span className="analytics-card-label">ANALYSIS RECORDS</span><h2>{isLoading ? "…" : error ? "—" : records.length}</h2><p>Real records reported by `/api/analysis/history`.</p></div></article>
        <article className="analytics-card"><div className="analytics-card-icon"><CheckCircle2 size={18} /></div><div className="analytics-card-content"><span className="analytics-card-label">SUCCESSFUL</span><h2>{isLoading ? "…" : error ? "—" : stats.success}</h2><p>Backend records whose status is success.</p></div></article>
        <article className="analytics-card"><div className="analytics-card-icon"><Clock3 size={18} /></div><div className="analytics-card-content"><span className="analytics-card-label">BLOCKED / FAILED</span><h2>{isLoading ? "…" : error ? "—" : stats.blocked + stats.failed}</h2><p>{isLoading ? "Loading" : error ? "History could not be loaded" : `${stats.blocked} blocked · ${stats.failed} failed`}</p></div></article>
      </div>

      {records.length === 0 && !isLoading && !error ? (
        <div className="analytics-empty-state"><div className="analytics-empty-icon"><BarChart3 size={24} /></div><div><h2>No analysis records yet</h2><p>Run a real analysis to populate activity counts. Model accuracy and geographic statistics are not available from the history endpoint.</p><button type="button" className="record-action" onClick={openNewScan}>Open New Scan</button></div></div>
      ) : (
        <p className="page-data-note">This view reports activity counts only. The backend does not persist records across restarts or provide evaluation metrics, so no model-performance charts are shown.</p>
      )}
    </section>
  );
}

export default Analytics;
