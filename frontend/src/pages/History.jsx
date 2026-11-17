import { useMemo, useRef, useState } from "react";
import { Clock3, Search, Satellite } from "lucide-react";
import AnalysisSummary from "../components/analysis/AnalysisSummary";
import useBackendHistory from "../hooks/useBackendHistory";
import { getAnalysis } from "../services/analysisApi";
import useNewScan from "../hooks/useNewScan";

function History() {
  const { records, isLoading, error, refresh } = useBackendHistory();
  const openNewScan = useNewScan();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [expandedId, setExpandedId] = useState(null);
  const [expandedResult, setExpandedResult] = useState(null);
  const [detailError, setDetailError] = useState(null);
  const [loadingId, setLoadingId] = useState(null);
  const detailRequestId = useRef(0);

  const filtered = useMemo(() => records.filter((record) => {
    const matchesText = record.query?.toLowerCase().includes(search.trim().toLowerCase());
    const matchesStatus = statusFilter === "all" || record.status === statusFilter;
    return matchesText && matchesStatus;
  }), [records, search, statusFilter]);

  const toggleDetails = async (analysisId) => {
    if (expandedId === analysisId) {
      detailRequestId.current += 1;
      setExpandedId(null);
      setExpandedResult(null);
      setDetailError(null);
      return;
    }
    const requestId = ++detailRequestId.current;
    setExpandedId(analysisId);
    setExpandedResult(null);
    setDetailError(null);
    setLoadingId(analysisId);
    try {
      const result = await getAnalysis(analysisId);
      if (requestId === detailRequestId.current) setExpandedResult(result);
    } catch (requestError) {
      if (requestId === detailRequestId.current) {
        setDetailError(requestError?.message || "Unable to load this analysis result.");
      }
    } finally {
      if (requestId === detailRequestId.current) setLoadingId(null);
    }
  };

  return (
    <section className="page-shell history-page">
      <div className="page-header">
        <div className="page-heading">
          <div className="page-eyebrow"><span className="page-eyebrow-line" /><span>WORKSPACE HISTORY</span></div>
          <h1>Analysis History</h1>
          <p>Real analysis records held by the current backend process.</p>
        </div>
        <div className="page-status"><span className="page-status-dot" /><span>{isLoading ? "LOADING" : `${records.length} RECORDS`}</span></div>
      </div>

      <div className="history-toolbar">
        <label className="history-search">
          <Search size={15} />
          <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search analysis history..." aria-label="Search analysis history" />
        </label>
        <select className="history-filter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="Filter history by status">
          <option value="all">All statuses</option>
          <option value="success">Successful</option>
          <option value="blocked">Blocked</option>
          <option value="failed">Failed</option>
        </select>
        <button type="button" className="record-action" onClick={refresh} disabled={isLoading}>Refresh</button>
      </div>

      {error && <p className="page-error" role="alert">{error} <button type="button" className="record-action" onClick={refresh}>Retry</button></p>}
      {error ? null : isLoading ? <p className="page-feedback">Loading backend analysis records…</p> : filtered.length ? (
        <div className="record-list">
          {filtered.map((record) => (
            <article className="record-card record-card-stacked" key={record.analysis_id}>
              <div className="record-card-row">
                <Clock3 size={18} />
                <div className="record-card-main">
                  <h2>{record.query || "Analysis request"}</h2>
                  <p>Analysis ID: <code>{record.analysis_id}</code></p>
                </div>
                <span className={`status-chip status-${record.status || "unknown"}`}>{record.status || "unknown"}</span>
                <button type="button" className="record-action" onClick={() => toggleDetails(record.analysis_id)} disabled={loadingId === record.analysis_id}>
                  {loadingId === record.analysis_id ? "Loading…" : expandedId === record.analysis_id ? "Hide result" : "View result"}
                </button>
              </div>
              {expandedId === record.analysis_id && (
                <div className="record-details">
                  {detailError && <p className="page-error" role="alert">{detailError}</p>}
                  {expandedResult && <AnalysisSummary analysis={expandedResult} />}
                </div>
              )}
            </article>
          ))}
        </div>
      ) : (
        <div className="page-empty-state">
          <Satellite size={24} />
          <h2>{records.length ? "No matching records" : "No analysis records available"}</h2>
          <p>{records.length ? "Change the search or status filter." : "The backend history is empty. Records are in memory and reset when the backend process restarts."}</p>
          {!records.length && <button type="button" className="record-action" onClick={openNewScan}>Start a scan</button>}
        </div>
      )}

      <div className="history-preview">
        <div className="history-preview-item"><span>ANALYSIS RECORDS</span><strong>{isLoading ? "…" : records.length}</strong></div>
        <div className="history-preview-item"><span>QUERIES</span><strong>{isLoading ? "…" : new Set(records.map((record) => record.query)).size}</strong></div>
        <div className="history-preview-item"><span>STORAGE</span><strong>Current process</strong></div>
      </div>
    </section>
  );
}

export default History;
