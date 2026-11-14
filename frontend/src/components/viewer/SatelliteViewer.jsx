import { useEffect, useRef, useState } from "react";
import {
  Layers3,
  Upload,
  X,
} from "lucide-react";

import useImageViewer from "../../hooks/useImageViewer";
import {
  formatFileSize,
  getImageMetadata,
  isSupportedImage,
} from "../../utils/imageUtils";
import ImageToolbar from "./ImageToolbar";
import LayerControls from "./LayerControls";
import BeforeAfterSlider from "./BeforeAfterSlider";
import OverlayRenderer from "./OverlayRenderer";

function SatelliteViewer() {
  const viewerRef = useRef(null);
  const fileInputRef = useRef(null);

  const {
    image,
    zoom,
    position,
    isDragging,
    uploadImage,
    clearImage,
    zoomIn,
    zoomOut,
    resetView,
    startPan,
    moveImage,
    endPan,
  } = useImageViewer();

  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isLayersOpen, setIsLayersOpen] = useState(false);

  const [layers, setLayers] = useState({
    baseImage: true,
    analysis: false,
    buildings: false,
    water: false,
    vegetation: false,
  });

  const [imageMetadata, setImageMetadata] = useState(null);
  const [uploadError, setUploadError] = useState("");

  /*
   * Placeholder overlay data.
   *
   * Real CV results will be supplied by the backend later.
   * No fabricated detection/segmentation result is rendered.
   */
  const overlayData = {
    boxes: [],
    regions: [],
    points: [],
  };

  useEffect(() => {
    if (!image?.file) {
      setImageMetadata(null);
      return;
    }

    setImageMetadata(getImageMetadata(image.file));
  }, [image]);

  useEffect(() => {
    const handleFullscreenChange = () => {
      const active =
        document.fullscreenElement === viewerRef.current;

      setIsFullscreen(active);
    };

    document.addEventListener(
      "fullscreenchange",
      handleFullscreenChange
    );

    return () => {
      document.removeEventListener(
        "fullscreenchange",
        handleFullscreenChange
      );
    };
  }, []);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    setUploadError("");

    if (!isSupportedImage(file)) {
      setUploadError(
        "Unsupported image format. Use JPG, JPEG, PNG, or WEBP."
      );

      event.target.value = "";
      return;
    }

    uploadImage(file);

    event.target.value = "";
  };

  const handleFullscreen = async () => {
    try {
      if (!document.fullscreenElement) {
        await viewerRef.current?.requestFullscreen();
      } else {
        await document.exitFullscreen();
      }
    } catch (error) {
      console.error("Fullscreen error:", error);
    }
  };

  const handleWheel = (event) => {
    if (!image) {
      return;
    }

    if (event.deltaY < 0) {
      zoomIn();
    } else {
      zoomOut();
    }
  };

  const handlePointerDown = (event) => {
    if (!image || zoom <= 1) {
      return;
    }

    event.currentTarget.setPointerCapture(
      event.pointerId
    );

    startPan();
  };

  const handlePointerMove = (event) => {
    if (!isDragging) {
      return;
    }

    moveImage(
      event.nativeEvent.offsetX,
      event.nativeEvent.offsetY
    );
  };

  const handlePointerUp = (event) => {
    if (
      event.currentTarget.hasPointerCapture(
        event.pointerId
      )
    ) {
      event.currentTarget.releasePointerCapture(
        event.pointerId
      );
    }

    endPan();
  };

  const handlePointerCancel = () => {
    endPan();
  };

  const toggleLayer = (layerKey) => {
    setLayers((currentLayers) => ({
      ...currentLayers,
      [layerKey]: !currentLayers[layerKey],
    }));
  };

  const imageTransform = {
    transform: `translate(${position.x}px, ${position.y}px) scale(${zoom})`,
  };

  return (
    <section
      ref={viewerRef}
      className={`satellite-viewer ${
        isFullscreen ? "is-fullscreen" : ""
      }`}
    >
      <div className="viewer-header">
        <div className="viewer-header-left">
          <div className="viewer-title-group">
            <span className="viewer-kicker">
              IMAGE VIEWER
            </span>

            <h2>Satellite Scene</h2>
          </div>

          {imageMetadata && (
            <div className="viewer-image-meta">
              <span className="viewer-image-name">
                {imageMetadata.name}
              </span>

              <span className="viewer-image-details">
                {imageMetadata.format}
                {" • "}
                {formatFileSize(imageMetadata.size)}
              </span>
            </div>
          )}
        </div>

        <div className="viewer-header-actions">
          <div className="viewer-layer-control">
            <button
              type="button"
              className={`viewer-icon-button ${
                isLayersOpen ? "active" : ""
              }`}
              onClick={() =>
                setIsLayersOpen(
                  (current) => !current
                )
              }
              aria-label="Toggle scene layers"
              title="Scene layers"
            >
              <Layers3
                size={15}
                strokeWidth={1.7}
              />
            </button>

            <LayerControls
              isOpen={isLayersOpen}
              layers={layers}
              onToggle={toggleLayer}
              onClose={() =>
                setIsLayersOpen(false)
              }
            />
          </div>

          {image && (
            <button
              type="button"
              className="viewer-clear-button"
              onClick={clearImage}
              aria-label="Remove image"
              title="Remove image"
            >
              <X
                size={14}
                strokeWidth={1.8}
              />
            </button>
          )}
        </div>
      </div>

      <div
        className={`viewer-canvas ${
          isDragging ? "is-dragging" : ""
        }`}
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerCancel}
      >
        {!image ? (
          <div className="viewer-empty-state">
            <div className="viewer-empty-icon">
              <Upload
                size={22}
                strokeWidth={1.5}
              />
            </div>

            <div className="viewer-empty-content">
              <span className="viewer-empty-kicker">
                SATELLITE IMAGERY
              </span>

              <h3>
                Upload an image to begin analysis
              </h3>

              <p>
                Add a satellite image and explore it
                through natural-language analysis.
              </p>

              <button
                type="button"
                className="viewer-upload-button"
                onClick={handleUploadClick}
              >
                <Upload
                  size={14}
                  strokeWidth={1.8}
                />
                <span>Upload Image</span>
              </button>

              <span className="viewer-supported-formats">
                JPG · JPEG · PNG · WEBP
              </span>

              {uploadError && (
                <div className="viewer-upload-error">
                  {uploadError}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="viewer-image-stage">
            {layers.baseImage && (
              <img
                src={image.url}
                alt={`Satellite scene: ${image.name}`}
                className="viewer-image"
                style={imageTransform}
                draggable={false}
              />
            )}

            <OverlayRenderer
              visible={
                layers.analysis &&
                overlayData.boxes.length > 0
              }
              type="boxes"
              data={overlayData.boxes}
            />

            <OverlayRenderer
              visible={
                layers.analysis &&
                overlayData.regions.length > 0
              }
              type="regions"
              data={overlayData.regions}
            />

            <OverlayRenderer
              visible={
                layers.analysis &&
                overlayData.points.length > 0
              }
              type="points"
              data={overlayData.points}
            />

            <div className="viewer-image-badge">
              <span className="viewer-badge-dot" />
              <span>LOCAL IMAGE</span>
            </div>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={handleFileChange}
          hidden
        />

        {image && (
          <ImageToolbar
            image={image}
            zoom={zoom}
            onZoomIn={zoomIn}
            onZoomOut={zoomOut}
            onReset={resetView}
            onFullscreen={handleFullscreen}
          />
        )}
      </div>

      {image && (
        <div className="viewer-footer">
          <div className="viewer-footer-left">
            <span>
              ZOOM {Math.round(zoom * 100)}%
            </span>

            <span className="viewer-footer-divider" />

            <span>
              {imageMetadata?.format ?? "IMAGE"}
            </span>
          </div>

          <div className="viewer-footer-right">
            <span>
              Scroll to zoom
            </span>

            <span className="viewer-footer-divider" />

            <span>
              Drag to pan
            </span>
          </div>
        </div>
      )}

      {/*
       * BeforeAfterSlider is intentionally kept as a
       * standalone viewer capability.
       *
       * It will receive real before/after imagery when
       * LEVIR-CD change detection is connected.
       */}
      {false && (
        <BeforeAfterSlider
          beforeImage={null}
          afterImage={null}
        />
      )}
    </section>
  );
}

export default SatelliteViewer;