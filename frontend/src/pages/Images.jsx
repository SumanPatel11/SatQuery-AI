import { ImagePlus, Satellite } from "lucide-react";
import { useAppContext } from "../context/AppContext";
import useNewScan from "../hooks/useNewScan";

function Images() {
  const { selectedImage, selectedSecondImage } = useAppContext();
  const openNewScan = useNewScan();
  const images = [
    selectedImage && { role: "Before / primary image", ...selectedImage },
    selectedSecondImage && { role: "After / comparison image", ...selectedSecondImage },
  ].filter(Boolean);

  return (
    <section className="page-shell">
      <div className="page-header">
        <div className="page-heading">
          <div className="page-eyebrow"><span className="page-eyebrow-line" /><span>IMAGE LIBRARY</span></div>
          <h1>Images</h1>
          <p>Uploaded image selections currently held by this workspace.</p>
        </div>
        <div className="page-status"><span className="page-status-dot" /><span>{images.length} CURRENT SELECTION{images.length === 1 ? "" : "S"}</span></div>
      </div>

      {images.length ? (
        <div className="record-list">
          {images.map((image) => (
            <article className="record-card" key={`${image.role}-${image.image_id || image.name}`}>
              <ImagePlus size={18} />
              <div className="record-card-main">
                <h2>{image.name || "Unnamed upload"}</h2>
                <p>{image.role} · upload {image.uploadStatus || "unknown"}</p>
                {image.image_id && <code>Image ID: {image.image_id}</code>}
                {Number.isFinite(image.size) && <span>{(image.size / (1024 * 1024)).toFixed(2)} MB</span>}
              </div>
              <button type="button" className="record-action" onClick={openNewScan}>
                Open in scan workspace
              </button>
            </article>
          ))}
        </div>
      ) : (
        <div className="page-empty-state">
          <Satellite size={24} />
          <h2>No image selected</h2>
          <p>Upload an image from New Scan to see its current selection here.</p>
          <button type="button" className="record-action" onClick={openNewScan}>Go to New Scan</button>
        </div>
      )}

      <p className="page-data-note">The backend stores uploaded files but does not expose an image-list endpoint. This page shows only the real primary and comparison selections held in the current browser session; it is not a persistent image library.</p>
    </section>
  );
}

export default Images;
