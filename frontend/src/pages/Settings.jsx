import { useState } from "react";
import { Cpu, Globe2, Palette, Satellite, SlidersHorizontal } from "lucide-react";
import api from "../services/api";

const tabs = [
  { id: "general", label: "General", icon: SlidersHorizontal },
  { id: "engine", label: "AI Engine", icon: Cpu },
  { id: "workspace", label: "Workspace", icon: Globe2 },
];

function Settings() {
  const [activeTab, setActiveTab] = useState("general");
  const [backendStatus, setBackendStatus] = useState("Not checked");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState(null);

  const checkBackend = async () => {
    setChecking(true);
    setError(null);
    try {
      const result = await api.getHealth();
      setBackendStatus(`${result.service || "Backend"} · ${result.status || "online"}`);
    } catch (requestError) {
      setBackendStatus("Offline");
      setError(requestError?.message || "Backend health check failed.");
    } finally {
      setChecking(false);
    }
  };

  return (
    <section className="page-shell settings-page">
      <div className="page-header">
        <div className="page-heading">
          <div className="page-eyebrow"><span className="page-eyebrow-line" /><span>WORKSPACE CONFIGURATION</span></div>
          <h1>Settings</h1>
          <p>Inspect available local application and backend settings.</p>
        </div>
        <div className="page-status"><span className="page-status-dot" /><span>LOCAL DEMO</span></div>
      </div>

      <div className="settings-layout">
        <nav className="settings-navigation" aria-label="Settings sections">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button key={id} type="button" className={`settings-nav-item ${activeTab === id ? "active" : ""}`} onClick={() => setActiveTab(id)} aria-pressed={activeTab === id}>
              <Icon size={15} strokeWidth={1.7} /><span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="settings-content">
          {activeTab === "general" && (
            <section className="settings-card">
              <div className="settings-card-header"><div className="settings-card-icon"><Palette size={17} /></div><div><h2>Interface</h2><p>The visual theme is provided by the existing SatQuery workspace.</p></div></div>
              <div className="settings-card-items">
                <div className="settings-row"><span className="settings-row-label">Workspace theme</span><span className="settings-row-value">Dark satellite intelligence</span></div>
                <div className="settings-row"><span className="settings-row-label">Viewer controls</span><span className="settings-row-value">Pan, zoom and fullscreen</span></div>
              </div>
            </section>
          )}

          {activeTab === "engine" && (
            <section className="settings-card">
              <div className="settings-card-header"><div className="settings-card-icon"><Cpu size={17} /></div><div><h2>AI Engine</h2><p>Check the configured FastAPI service. Model execution is triggered by analysis requests.</p></div></div>
              <div className="settings-card-items">
                <div className="settings-row"><span className="settings-row-label">Backend health</span><span className="settings-row-value">{backendStatus}</span></div>
                <div className="settings-row"><span className="settings-row-label">Analysis pipeline</span><span className="settings-row-value">M1 · Ollama/Qwen3 · planner · CV registry</span></div>
              </div>
              <div className="settings-actions"><button type="button" className="record-action" onClick={checkBackend} disabled={checking}>{checking ? "Checking…" : "Check backend connection"}</button>{error && <p className="page-error" role="alert">{error}</p>}</div>
            </section>
          )}

          {activeTab === "workspace" && (
            <section className="settings-card">
              <div className="settings-card-header"><div className="settings-card-icon"><Globe2 size={17} /></div><div><h2>Workspace data</h2><p>Current persistence behavior reported by the existing application.</p></div></div>
              <div className="settings-card-items">
                <div className="settings-row"><span className="settings-row-label">Analysis history</span><span className="settings-row-value">Current backend process memory</span></div>
                <div className="settings-row"><span className="settings-row-label">Image library</span><span className="settings-row-value">No backend image-list API; current selections only</span></div>
                <div className="settings-row"><span className="settings-row-label">Session/context chat</span><span className="settings-row-value">Not persisted or used by analysis</span></div>
              </div>
            </section>
          )}

          <div className="settings-system-card"><div className="settings-system-icon"><Satellite size={18} /></div><div><span className="settings-system-label">SATQUERY AI</span><h3>Settings reflect available functionality</h3><p>Unsupported notification, persistence, and model-performance controls are not represented as editable settings.</p></div></div>
        </div>
      </div>
    </section>
  );
}

export default Settings;
