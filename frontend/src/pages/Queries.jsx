import { useMemo, useState } from "react";
import { MessageSquareText, Search } from "lucide-react";
import useBackendHistory from "../hooks/useBackendHistory";
import useNewScan from "../hooks/useNewScan";

function Queries() {
  const { records, isLoading, error, refresh } = useBackendHistory();
  const openNewScan = useNewScan();
  const [search, setSearch] = useState("");
  const filtered = useMemo(
    () => records.filter((record) => record.query?.toLowerCase().includes(search.trim().toLowerCase())),
    [records, search]
  );

  return (
    <section className="page-shell">
      <div className="page-header">
        <div className="page-heading">
          <div className="page-eyebrow"><span className="page-eyebrow-line" /><span>QUERY LOG</span></div>
          <h1>Queries</h1>
          <p>Natural-language queries recorded by the running backend.</p>
        </div>
        <div className="page-status"><span className="page-status-dot" /><span>{isLoading ? "LOADING" : `${records.length} QUERIES`}</span></div>
      </div>

      <label className="record-search"><Search size={15} /><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search recorded queries" /></label>
      {error && <div className="page-error" role="alert">{error} <button type="button" className="record-action" onClick={refresh}>Retry</button></div>}
      {error ? null : isLoading ? <p className="page-feedback">Loading backend query records…</p> : filtered.length ? (
        <div className="record-list">
          {filtered.map((record) => (
            <article className="record-card" key={record.analysis_id}>
              <MessageSquareText size={18} />
              <div className="record-card-main">
                <h2>{record.query}</h2>
                <p>Analysis ID: <code>{record.analysis_id}</code></p>
              </div>
              <span className={`status-chip status-${record.status || "unknown"}`}>{record.status || "unknown"}</span>
            </article>
          ))}
        </div>
      ) : (
        <div className="page-empty-state">
          <MessageSquareText size={24} />
          <h2>{records.length ? "No matching queries" : "No query records available"}</h2>
          <p>{records.length ? "Try a different search." : "The backend has no analysis records in its current process. Records are not persisted across backend restarts."}</p>
          {!records.length && <button type="button" className="record-action" onClick={openNewScan}>Start a scan</button>}
        </div>
      )}
      <p className="page-data-note">Query entries come from the backend analysis-history API; this application does not maintain a separate persistent query log.</p>
    </section>
  );
}

export default Queries;
