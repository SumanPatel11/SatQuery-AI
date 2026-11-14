import { useEffect } from "react";
import { X } from "lucide-react";

function Modal({
  isOpen,
  onClose,
  title,
  subtitle = "",
  children,
  size = "md",
  closeOnOverlay = true,
  showCloseButton = true,
}) {
  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        onClose?.();
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  const handleOverlayClick = (event) => {
    if (
      closeOnOverlay &&
      event.target === event.currentTarget
    ) {
      onClose?.();
    }
  };

  return (
    <div
      className="sq-modal-overlay"
      onMouseDown={handleOverlayClick}
      role="presentation"
    >
      <div
        className={`sq-modal sq-modal-${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? "sq-modal-title" : undefined}
      >
        <div className="sq-modal-header">
          <div className="sq-modal-heading">
            {title && (
              <h2 id="sq-modal-title">
                {title}
              </h2>
            )}

            {subtitle && (
              <p>{subtitle}</p>
            )}
          </div>

          {showCloseButton && (
            <button
              type="button"
              className="sq-modal-close"
              onClick={onClose}
              aria-label="Close modal"
              title="Close"
            >
              <X size={16} strokeWidth={1.8} />
            </button>
          )}
        </div>

        <div className="sq-modal-body">
          {children}
        </div>
      </div>
    </div>
  );
}

export default Modal;