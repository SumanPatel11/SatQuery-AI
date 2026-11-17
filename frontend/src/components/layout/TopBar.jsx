import { useEffect, useState } from "react";
import { Bell, CircleHelp, Command, Satellite } from "lucide-react";
import Modal from "../common/Modal";
import api from "../../services/api";
import { useSessionContext } from "../../context/SessionContext";

function TopBar() {
  const { currentWorkspace } = useSessionContext();
  const [backendStatus, setBackendStatus] = useState("Checking backend");
  const [isHelpOpen, setIsHelpOpen] = useState(false);

  useEffect(() => {
    let active = true;
    api.getHealth().then(() => {
      if (active) setBackendStatus("Backend online");
    }).catch(() => {
      if (active) setBackendStatus("Backend offline");
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const handleShortcut = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setIsHelpOpen(true);
      }
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="breadcrumb">
          <span className="breadcrumb-muted">SatQuery AI</span>
          <span className="breadcrumb-separator">/</span>
          <span className="breadcrumb-current">{currentWorkspace}</span>
        </div>
      </div>

      <div className="topbar-right">
        <div className="engine-status" title="Status from the FastAPI health endpoint">
          <span className="engine-indicator" />
          <span>{backendStatus.toUpperCase()}</span>
        </div>
        <div className="topbar-divider" />
        <button type="button" className="topbar-icon" aria-label="Help and documentation" title="Help and demonstration guide" onClick={() => setIsHelpOpen(true)}>
          <CircleHelp size={16} strokeWidth={1.7} />
        </button>
        <button type="button" className="topbar-icon" aria-label="Notifications" title="Notifications are not configured for this local demo" disabled>
          <Bell size={16} strokeWidth={1.7} />
        </button>
        <button type="button" className="shortcut" aria-label="Open help" title="Open help" onClick={() => setIsHelpOpen(true)}>
          <Command size={12} strokeWidth={1.7} /><span>K</span>
        </button>
        <div className="profile">
          <div className="profile-avatar">SP</div>
          <div className="profile-info">
            <span className="profile-name">Suman</span>
            <span className="profile-role">Analyst</span>
          </div>
        </div>
        <div className="satellite-status" title="Satellite workspace">
          <Satellite size={14} strokeWidth={1.7} />
        </div>
      </div>

      <Modal isOpen={isHelpOpen} onClose={() => setIsHelpOpen(false)} title="SatQuery AI quick guide" subtitle="Local satellite image analysis">
        <ul className="help-list">
          <li>Open New Scan and upload the image you want to analyze.</li>
          <li>Use natural-language queries for building detection, land-cover segmentation, and flood detection.</li>
          <li>For building change detection, upload a before image and an after image in that order.</li>
          <li>Flood detection requires a compatible two-band SAR GeoTIFF.</li>
          <li>Analysis history is held in the current backend process and clears when that process restarts.</li>
        </ul>
      </Modal>
    </header>
  );
}

export default TopBar;
