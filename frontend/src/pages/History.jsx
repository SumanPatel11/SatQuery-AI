import {
  Clock3,
  FileImage,
  Search,
  Satellite,
} from "lucide-react";

function History() {
  return (
    <section className="page-shell history-page">
      <div className="page-header">
        <div className="page-heading">
          <div className="page-eyebrow">
            <span className="page-eyebrow-line" />
            <span>WORKSPACE HISTORY</span>
          </div>

          <h1>Analysis History</h1>

          <p>
            Access previously processed satellite imagery,
            queries, and analysis sessions.
          </p>
        </div>

        <div className="page-status">
          <span className="page-status-dot" />
          <span>NO SESSIONS</span>
        </div>
      </div>

      <div className="history-toolbar">
        <div className="history-search">
          <Search size={15} strokeWidth={1.7} />

          <input
            type="search"
            placeholder="Search analysis history..."
            aria-label="Search analysis history"
          />
        </div>

        <button
          type="button"
          className="history-filter"
        >
          <Clock3 size={14} strokeWidth={1.7} />
          <span>All Sessions</span>
        </button>
      </div>

      <div className="history-empty-state">
        <div className="history-empty-icon">
          <Satellite size={24} strokeWidth={1.5} />
        </div>

        <div className="history-empty-content">
          <div className="history-empty-kicker">
            ANALYSIS HISTORY
          </div>

          <h2>No analysis sessions yet</h2>

          <p>
            Completed image analyses and natural-language
            queries will appear here once the backend
            processing pipeline is connected.
          </p>
        </div>
      </div>

      <div className="history-preview">
        <div className="history-preview-item">
          <FileImage size={16} strokeWidth={1.6} />

          <div>
            <span>IMAGE ANALYSES</span>
            <strong>—</strong>
          </div>
        </div>

        <div className="history-preview-item">
          <Search size={16} strokeWidth={1.6} />

          <div>
            <span>QUERIES PROCESSED</span>
            <strong>—</strong>
          </div>
        </div>

        <div className="history-preview-item">
          <Clock3 size={16} strokeWidth={1.6} />

          <div>
            <span>RECENT SESSION</span>
            <strong>—</strong>
          </div>
        </div>
      </div>
    </section>
  );
}

export default History;