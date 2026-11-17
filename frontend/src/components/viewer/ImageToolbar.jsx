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
  onZoomIn,
  onZoomOut,
  onReset,
  onFullscreen,
}) {
  return (
    <div className="viewer-toolbar">
      <button
        type="button"
        className="viewer-tool"
        disabled
        aria-label="Select"
        title="Selection mode is not available; use drag to pan the image."
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
        disabled
        aria-label="Map"
        title="Map layers are not configured for this local demo."
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
