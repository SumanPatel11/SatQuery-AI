import {
  Bell,
  CircleHelp,
  Command,
  Satellite,
} from "lucide-react";

function TopBar() {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="breadcrumb">
          <span className="breadcrumb-muted">Workspace</span>

          <span className="breadcrumb-separator">/</span>

          <span className="breadcrumb-current">
            New Scan
          </span>
        </div>
      </div>

      <div className="topbar-right">
        <div className="engine-status">
          <span className="engine-indicator" />
          <span>AI ENGINE READY</span>
        </div>

        <div className="topbar-divider" />

        <button
          type="button"
          className="topbar-icon"
          aria-label="Help and documentation"
        >
          <CircleHelp
            size={16}
            strokeWidth={1.7}
          />
        </button>

        <button
          type="button"
          className="topbar-icon"
          aria-label="Notifications"
        >
          <Bell
            size={16}
            strokeWidth={1.7}
          />
        </button>

        <div
          className="shortcut"
          aria-label="Keyboard shortcut"
        >
          <Command
            size={12}
            strokeWidth={1.7}
          />
          <span>K</span>
        </div>

        <div className="profile">
          <div className="profile-avatar">
            SP
          </div>

          <div className="profile-info">
            <span className="profile-name">
              Suman
            </span>

            <span className="profile-role">
              Analyst
            </span>
          </div>
        </div>

        <div
          className="satellite-status"
          title="Satellite workspace"
        >
          <Satellite
            size={14}
            strokeWidth={1.7}
          />
        </div>
      </div>
    </header>
  );
}

export default TopBar;