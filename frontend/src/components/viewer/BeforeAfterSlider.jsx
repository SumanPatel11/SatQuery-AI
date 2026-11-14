import { useEffect, useRef, useState } from "react";

function BeforeAfterSlider({
  beforeImage,
  afterImage,
  beforeLabel = "BEFORE",
  afterLabel = "AFTER",
}) {
  const containerRef = useRef(null);

  const [sliderPosition, setSliderPosition] = useState(50);
  const [isDragging, setIsDragging] = useState(false);

  const updateSliderPosition = (clientX) => {
    if (!containerRef.current) {
      return;
    }

    const rect = containerRef.current.getBoundingClientRect();

    const position =
      ((clientX - rect.left) / rect.width) * 100;

    setSliderPosition(
      Math.min(Math.max(position, 0), 100)
    );
  };

  const handlePointerDown = (event) => {
    event.preventDefault();

    event.currentTarget.setPointerCapture(
      event.pointerId
    );

    setIsDragging(true);

    updateSliderPosition(event.clientX);
  };

  const handlePointerMove = (event) => {
    if (!isDragging) {
      return;
    }

    updateSliderPosition(event.clientX);
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

    setIsDragging(false);
  };

  const handlePointerCancel = () => {
    setIsDragging(false);
  };

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (!isDragging) {
        return;
      }

      if (event.key === "ArrowLeft") {
        setSliderPosition((current) =>
          Math.max(current - 1, 0)
        );
      }

      if (event.key === "ArrowRight") {
        setSliderPosition((current) =>
          Math.min(current + 1, 100)
        );
      }
    };

    window.addEventListener(
      "keydown",
      handleKeyDown
    );

    return () => {
      window.removeEventListener(
        "keydown",
        handleKeyDown
      );
    };
  }, [isDragging]);

  if (!beforeImage || !afterImage) {
    return null;
  }

  return (
    <div
      ref={containerRef}
      className="before-after-slider"
    >
      <img
        src={beforeImage}
        alt="Before scene"
        className="before-after-image before-image"
      />

      <div
        className="before-after-after"
        style={{
          width: `${sliderPosition}%`,
        }}
      >
        <img
          src={afterImage}
          alt="After scene"
          className="before-after-image after-image"
        />
      </div>

      <div className="before-after-label before-label">
        {beforeLabel}
      </div>

      <div className="before-after-label after-label">
        {afterLabel}
      </div>

      <div
        className={`before-after-handle ${
          isDragging ? "dragging" : ""
        }`}
        style={{
          left: `${sliderPosition}%`,
        }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerCancel}
        role="slider"
        tabIndex={0}
        aria-label="Before and after comparison"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(sliderPosition)}
      >
        <div className="before-after-handle-line" />

        <div className="before-after-handle-button">
          <span />
          <span />
        </div>
      </div>
    </div>
  );
}

export default BeforeAfterSlider;