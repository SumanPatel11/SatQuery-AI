import { X } from "lucide-react";

function LayerControls({
  isOpen,
  layers,
  onToggle,
  onClose,
}) {
  if (!isOpen) {
    return null;
  }

  const layerItems = [
    {
      key: "baseImage",
      label: "Base Image",
      indicatorClass: "base",
    },
    {
      key: "analysis",
      label: "Analysis Overlay",
      indicatorClass: "analysis",
    },
    {
      key: "buildings",
      label: "Buildings",
      indicatorClass: "buildings",
    },
    {
      key: "water",
      label: "Water",
      indicatorClass: "water",
    },
    {
      key: "vegetation",
      label: "Vegetation",
      indicatorClass: "vegetation",
    },
  ];

  return (
    <div className="viewer-layer-panel">
      <div className="layer-panel-header">
        <div>
          <span className="layer-panel-kicker">
            VIEW LAYERS
          </span>

          <h3>Scene Layers</h3>
        </div>

        <button
          type="button"
          className="layer-panel-close"
          onClick={onClose}
          aria-label="Close layers"
          title="Close layers"
        >
          <X size={13} strokeWidth={1.8} />
        </button>
      </div>

      <div className="layer-list">
        {layerItems.map((layer) => (
          <button
            key={layer.key}
            type="button"
            className={`layer-item ${
              layers[layer.key] ? "active" : ""
            }`}
            onClick={() => onToggle(layer.key)}
          >
            <span className="layer-item-left">
              <span
                className={`layer-indicator ${layer.indicatorClass}`}
              />

              <span className="layer-item-name">
                {layer.label}
              </span>
            </span>

            <span className="layer-toggle">
              <span
                className={`layer-toggle-track ${
                  layers[layer.key] ? "on" : ""
                }`}
              >
                <span className="layer-toggle-thumb" />
              </span>
            </span>
          </button>
        ))}
      </div>

      <div className="layer-panel-note">
        Analysis layers will become available when model
        results are loaded.
      </div>
    </div>
  );
}

export default LayerControls;