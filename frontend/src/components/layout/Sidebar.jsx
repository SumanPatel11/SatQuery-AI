import {
  BarChart3,
  Clock3,
  ImagePlus,
  MessageSquareText,
  ScanSearch,
  Settings,
  Satellite,
} from "lucide-react";
import { useSessionContext } from "../../context/SessionContext";
import useNewScan from "../../hooks/useNewScan";

const navigationItems = [
  {
    label: "New Scan",
    icon: ScanSearch,
  },
  {
    label: "Images",
    icon: ImagePlus,
  },
  {
    label: "Queries",
    icon: MessageSquareText,
  },
  {
    label: "Analytics",
    icon: BarChart3,
  },
  {
    label: "History",
    icon: Clock3,
  },
];

function Sidebar() {
  const { currentWorkspace, setCurrentWorkspace } = useSessionContext();
  const openNewScan = useNewScan();

  const navigate = (label) => {
    if (label === "New Scan") {
      openNewScan();
      return;
    }
    setCurrentWorkspace(label);
  };

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <Satellite size={19} strokeWidth={1.7} />
        </div>

        <div className="brand-text">
          <div className="brand-name">SATQUERY</div>
          <div className="brand-subtitle">AI INTELLIGENCE</div>
        </div>
      </div>

      <div className="sidebar-section-label">WORKSPACE</div>

      <nav className="sidebar-nav" aria-label="Workspace navigation">
        {navigationItems.map((item) => {
          const Icon = item.icon;

          return (
            <button
              key={item.label}
              type="button"
              className={`nav-item ${currentWorkspace === item.label ? "active" : ""}`}
              onClick={() => navigate(item.label)}
              aria-current={currentWorkspace === item.label ? "page" : undefined}
            >
              <span className="nav-item-icon">
                <Icon size={16} strokeWidth={1.75} />
              </span>

              <span className="nav-item-label">{item.label}</span>

              {currentWorkspace === item.label && <span className="nav-active-indicator" />}
            </button>
          );
        })}
      </nav>

      <div className="sidebar-bottom">
        <button
          type="button"
          className={`nav-item sidebar-settings ${currentWorkspace === "Settings" ? "active" : ""}`}
          onClick={() => navigate("Settings")}
          aria-current={currentWorkspace === "Settings" ? "page" : undefined}
        >
          <span className="nav-item-icon">
            <Settings size={16} strokeWidth={1.75} />
          </span>

          <span className="nav-item-label">Settings</span>
        </button>

        <div className="system-status">
          <div className="system-status-indicator">
            <span className="status-dot" />
          </div>

          <div className="system-status-text">
            <div className="status-title">Local workspace</div>
            <div className="status-text">Backend status is shown above</div>
          </div>
        </div>

        <div className="version-label">
          SATQUERY AI <span>•</span> v0.1
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
