import {
  Expand,
  Map,
  Maximize2,
  Minus,
  MousePointer2,
  Plus,
} from "lucide-react";

function ImageToolbar({
  image,
  zoom,
  onZoomIn,
  onZoomOut,
  onReset,
  onFullscreen,
}) {
  return (
    <div className="viewer-toolbar">
      <button
        type="button"
        className="viewer-tool active"
        aria-label="Select"
        title="Select"
      >
        <MousePointer2
          size={15}
          strokeWidth={1.7}
        />
      </button>

      <div className="viewer-tool-divider" />

      <button
        type="button"
        className="viewer-tool"
        onClick={onZoomIn}
        disabled={!image}
        aria-label="Zoom in"
        title="Zoom in"
      >
        <Plus
          size={15}
          strokeWidth={1.7}
        />
      </button>

      <button
        type="button"
        className="viewer-tool"
        onClick={onZoomOut}
        disabled={!image}
        aria-label="Zoom out"
        title="Zoom out"
      >
        <Minus
          size={15}
          strokeWidth={1.7}
        />
      </button>

      <div className="viewer-tool-divider" />

      <button
        type="button"
        className="viewer-tool"
        onClick={onReset}
        disabled={!image}
        aria-label="Reset view"
        title="Reset view"
      >
        <Expand
          size={14}
          strokeWidth={1.7}
        />
      </button>

      <button
        type="button"
        className="viewer-tool"
        aria-label="Map"
        title="Map"
      >
        <Map
          size={15}
          strokeWidth={1.7}
        />
      </button>

      <button
        type="button"
        className="viewer-tool"
        onClick={onFullscreen}
        aria-label="Fullscreen"
        title="Fullscreen"
      >
        <Maximize2
          size={15}
          strokeWidth={1.7}
        />
      </button>
    </div>
  );
}

export default ImageToolbar;