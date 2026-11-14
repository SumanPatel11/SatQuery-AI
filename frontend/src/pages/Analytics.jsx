import {
  BarChart3,
  Database,
  LineChart,
  Satellite,
} from "lucide-react";

function Analytics() {
  return (
    <section className="page-shell analytics-page">
      <div className="page-header">
        <div className="page-heading">
          <div className="page-eyebrow">
            <span className="page-eyebrow-line" />
            <span>ANALYTICS</span>
          </div>

          <h1>Analysis Analytics</h1>

          <p>
            Review model performance and analysis activity
            across processed satellite imagery.
          </p>
        </div>

        <div className="page-status">
          <span className="page-status-dot" />
          <span>AWAITING DATA</span>
        </div>
      </div>

      <div className="analytics-grid">
        <div className="analytics-card">
          <div className="analytics-card-icon">
            <BarChart3 size={18} strokeWidth={1.7} />
          </div>

          <div className="analytics-card-content">
            <span className="analytics-card-label">
              MODEL PERFORMANCE
            </span>

            <h2>—</h2>

            <p>
              Metrics will appear after real model
              evaluations are available.
            </p>
          </div>
        </div>

        <div className="analytics-card">
          <div className="analytics-card-icon">
            <LineChart size={18} strokeWidth={1.7} />
          </div>

          <div className="analytics-card-content">
            <span className="analytics-card-label">
              ANALYSIS ACTIVITY
            </span>

            <h2>—</h2>

            <p>
              Analysis history will populate this
              section after backend integration.
            </p>
          </div>
        </div>

        <div className="analytics-card">
          <div className="analytics-card-icon">
            <Database size={18} strokeWidth={1.7} />
          </div>

          <div className="analytics-card-content">
            <span className="analytics-card-label">
              DATA PROCESSED
            </span>

            <h2>—</h2>

            <p>
              Dataset and processing statistics will be
              shown here when available.
            </p>
          </div>
        </div>
      </div>

      <div className="analytics-empty-state">
        <div className="analytics-empty-icon">
          <Satellite size={24} strokeWidth={1.5} />
        </div>

        <div>
          <h2>No analysis data yet</h2>

          <p>
            Run a real satellite image analysis to
            populate analytics and model performance
            information.
          </p>
        </div>
      </div>
    </section>
  );
}

export default Analytics;