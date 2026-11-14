import {
  Bell,
  Cpu,
  Globe2,
  Palette,
  Satellite,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";

const settingSections = [
  {
    icon: Palette,
    title: "Interface",
    description: "Workspace appearance and display preferences.",
    items: [
      {
        label: "Workspace Theme",
        value: "Satellite Intelligence",
      },
      {
        label: "Viewer Display",
        value: "Optimized",
      },
    ],
  },
  {
    icon: Cpu,
    title: "AI Engine",
    description: "Inference and model execution preferences.",
    items: [
      {
        label: "Inference Mode",
        value: "Automatic",
      },
      {
        label: "Processing",
        value: "Backend Pipeline",
      },
    ],
  },
  {
    icon: Bell,
    title: "Notifications",
    description: "Control workspace status notifications.",
    items: [
      {
        label: "Analysis Notifications",
        value: "Enabled",
      },
      {
        label: "System Alerts",
        value: "Enabled",
      },
    ],
  },
  {
    icon: ShieldCheck,
    title: "Privacy & Data",
    description: "Manage analysis data and session handling.",
    items: [
      {
        label: "Session Storage",
        value: "Local Session",
      },
      {
        label: "Image Retention",
        value: "Session Only",
      },
    ],
  },
];

function Settings() {
  return (
    <section className="page-shell settings-page">
      <div className="page-header">
        <div className="page-heading">
          <div className="page-eyebrow">
            <span className="page-eyebrow-line" />
            <span>WORKSPACE CONFIGURATION</span>
          </div>

          <h1>Settings</h1>

          <p>
            Configure the SatQuery AI workspace,
            analysis environment, and processing
            preferences.
          </p>
        </div>

        <div className="page-status">
          <span className="page-status-dot" />
          <span>CONFIGURATION</span>
        </div>
      </div>

      <div className="settings-layout">
        <aside className="settings-navigation">
          <button
            type="button"
            className="settings-nav-item active"
          >
            <SlidersHorizontal
              size={15}
              strokeWidth={1.7}
            />
            <span>General</span>
          </button>

          <button
            type="button"
            className="settings-nav-item"
          >
            <Cpu
              size={15}
              strokeWidth={1.7}
            />
            <span>AI Engine</span>
          </button>

          <button
            type="button"
            className="settings-nav-item"
          >
            <Globe2
              size={15}
              strokeWidth={1.7}
            />
            <span>Workspace</span>
          </button>
        </aside>

        <div className="settings-content">
          {settingSections.map((section) => {
            const Icon = section.icon;

            return (
              <section
                key={section.title}
                className="settings-card"
              >
                <div className="settings-card-header">
                  <div className="settings-card-icon">
                    <Icon
                      size={17}
                      strokeWidth={1.7}
                    />
                  </div>

                  <div>
                    <h2>{section.title}</h2>
                    <p>{section.description}</p>
                  </div>
                </div>

                <div className="settings-card-items">
                  {section.items.map((item) => (
                    <div
                      key={item.label}
                      className="settings-row"
                    >
                      <span className="settings-row-label">
                        {item.label}
                      </span>

                      <span className="settings-row-value">
                        {item.value}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            );
          })}

          <div className="settings-system-card">
            <div className="settings-system-icon">
              <Satellite
                size={18}
                strokeWidth={1.6}
              />
            </div>

            <div>
              <span className="settings-system-label">
                SATQUERY AI
              </span>

              <h3>Workspace configuration ready</h3>

              <p>
                Persistent settings and backend
                configuration will be connected during
                the integration phase.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default Settings;