import SatelliteViewer from "../viewer/SatelliteViewer";
import AnalysisPanel from "../analysis/AnalysisPanel";
import ChatPanel from "../chat/ChatPanel";
import useAnalysis from "../../hooks/useAnalysis";
import { ANALYSIS_STATUS } from "../../utils/constants";
import { useRef, useState } from "react";
import { useAppContext } from "../../context/AppContext";
import api from "../../services/api";
import { useSessionContext } from "../../context/SessionContext";
import {
  createGeoTiffPreview,
  isGeoTiff,
  isSupportedImage,
} from "../../utils/imageUtils";

function revokePreviewUrl(url) {
  if (typeof url === "string" && url.startsWith("blob:")) {
    URL.revokeObjectURL(url);
  }
}

function Workspace() {
  const { newScanToken } = useSessionContext();
  const { selectedSecondImage, setSelectedSecondImage } = useAppContext();
  const [secondImageError, setSecondImageError] = useState(null);
  const [secondImageUploading, setSecondImageUploading] = useState(false);
  const uploadId = useRef(0);
  const afterImageInputRef = useRef(null);
  const {
    analysisStatus,
    activeAnalysis,
    selectedImage,
    error,
    startAnalysis,
  } = useAnalysis();

  const panelStatus =
    analysisStatus === ANALYSIS_STATUS.IDLE
      ? "standby"
      : analysisStatus === ANALYSIS_STATUS.UPLOADING
        ? "processing"
        : analysisStatus === ANALYSIS_STATUS.PROCESSING
          ? "processing"
          : analysisStatus === ANALYSIS_STATUS.COMPLETED
            ? "completed"
            : analysisStatus === ANALYSIS_STATUS.ERROR
              ? "error"
              : "standby";

  const isImageReady =
    selectedImage?.uploadStatus === "uploaded" &&
    Boolean(selectedImage?.image_id);

  const isProcessing =
    analysisStatus === ANALYSIS_STATUS.PROCESSING;

  const selectAfterImage = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    setSecondImageError(null);
    if (!file) return;

    if (!isSupportedImage(file)) {
      setSecondImageError("Unsupported image format. Use JPG, JPEG, PNG, WEBP, or GeoTIFF.");
      return;
    }

    const requestId = ++uploadId.current;
    revokePreviewUrl(selectedSecondImage?.previewUrl);
    setSelectedSecondImage({ name: file.name, uploadStatus: "uploading" });
    setSecondImageUploading(true);
    let previewUrl = null;
    try {
      previewUrl = isGeoTiff(file)
        ? await createGeoTiffPreview(file)
        : URL.createObjectURL(file);
      if (requestId !== uploadId.current) {
        revokePreviewUrl(previewUrl);
        return;
      }

      setSelectedSecondImage({
        name: file.name,
        file,
        previewUrl,
        uploadStatus: "uploading",
      });

      const response = await api.uploadImage(file);
      if (requestId !== uploadId.current) {
        revokePreviewUrl(previewUrl);
        return;
      }
      if (!response?.image_id) throw new Error("Upload response did not contain an image ID.");
      setSelectedSecondImage({
        name: file.name,
        file,
        previewUrl,
        image_id: response.image_id,
        uploadStatus: "uploaded",
      });
    } catch (uploadError) {
      if (requestId === uploadId.current) {
        setSelectedSecondImage({
          name: file.name,
          file,
          previewUrl,
          uploadStatus: "failed",
        });
        setSecondImageError(uploadError.message || "After image upload failed.");
      } else {
        revokePreviewUrl(previewUrl);
      }
    } finally {
      if (requestId === uploadId.current) setSecondImageUploading(false);
    }
  };

  const clearAfterImage = () => {
    uploadId.current += 1;
    revokePreviewUrl(selectedSecondImage?.previewUrl);
    setSelectedSecondImage(null);
    setSecondImageUploading(false);
    setSecondImageError(null);
  };

  return (
    <section className="workspace">
      <div className="workspace-header">
        <div className="workspace-heading">
          <div className="workspace-eyebrow">
            <span className="eyebrow-line" />
            <span>MULTIMODAL REMOTE SENSING</span>
          </div>

          <h1>Satellite Intelligence Workspace</h1>

          <p>
            Analyze satellite imagery through natural-language queries.
          </p>
        </div>

        <div className="workspace-state">
          <span className="workspace-state-dot" />
          <span>READY FOR INPUT</span>
        </div>
      </div>

      <section className="after-image-control" aria-label="Building change comparison image">
        <div className="after-image-copy">
          <span className="after-image-kicker">OPTIONAL COMPARISON INPUT</span>
          <h2>After image</h2>
          <p>
            {selectedImage?.name
              ? `Before image: ${selectedImage.name}`
              : "Upload a before image first, then add the later image here."}
          </p>
          <p>Both images are used only for building-change analysis.</p>
        </div>

        <div className="after-image-actions">
          <input
            ref={afterImageInputRef}
            id="after-image"
            className="after-image-file-input"
            type="file"
            accept="image/*,.tif,.tiff"
            onChange={selectAfterImage}
            disabled={secondImageUploading || isProcessing}
            aria-label="Select after image"
          />
          <button
            type="button"
            className="after-image-select"
            onClick={() => afterImageInputRef.current?.click()}
            disabled={secondImageUploading || isProcessing}
          >
            {selectedSecondImage?.name ? "Replace after image" : "Select after image"}
          </button>
          {selectedSecondImage && (
            <button
              type="button"
              className="after-image-clear"
              onClick={clearAfterImage}
              disabled={isProcessing}
            >
              Clear
            </button>
          )}
          {secondImageUploading && <span className="after-image-status">Preparing and uploading…</span>}
          {selectedSecondImage?.uploadStatus === "uploaded" && (
            <span className="after-image-status after-image-status-ready">Uploaded</span>
          )}
          {secondImageError && <span className="after-image-error" role="alert">{secondImageError}</span>}
        </div>

        {selectedSecondImage?.previewUrl && (
          <figure className="after-image-preview">
            <img src={selectedSecondImage.previewUrl} alt={`After image preview: ${selectedSecondImage.name}`} />
            <figcaption>{selectedSecondImage.name}</figcaption>
          </figure>
        )}
      </section>

      <div className="workspace-grid">
        <div className="viewer-column">
          <SatelliteViewer />
        </div>

        <div className="analysis-column">
          <AnalysisPanel
            status={panelStatus}
            analysis={activeAnalysis}
          />

          {error && (
            <div className="chat-error" role="alert">
              {error}
            </div>
          )}
        </div>
      </div>

      <ChatPanel
        key={newScanToken}
        onAnalyze={(query) => startAnalysis({
          query,
          returnFailureDetails: true,
        })}
        disabled={!isImageReady || isProcessing || secondImageUploading}
      />
      {!isImageReady && (
        <p className="query-mode" role="status">
          Upload the before image and wait for it to finish before submitting an analysis.
        </p>
      )}
    </section>
  );
}

export default Workspace;
