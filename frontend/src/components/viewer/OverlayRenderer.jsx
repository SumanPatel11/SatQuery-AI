function OverlayRenderer({
  visible = false,
  type = null,
  data = null,
}) {
  if (!visible || !type || !data) {
    return null;
  }

  if (type === "boxes") {
    return (
      <div className="overlay-layer overlay-box-layer">
        {data.map((box, index) => (
          <div
            key={box.id ?? index}
            className="overlay-box"
            style={{
              left: `${box.x}%`,
              top: `${box.y}%`,
              width: `${box.width}%`,
              height: `${box.height}%`,
            }}
          >
            {box.label && (
              <span className="overlay-box-label">
                {box.label}
              </span>
            )}
          </div>
        ))}
      </div>
    );
  }

  if (type === "regions") {
    return (
      <div className="overlay-layer overlay-region-layer">
        {data.map((region, index) => (
          <div
            key={region.id ?? index}
            className={`overlay-region ${
              region.className ?? ""
            }`}
            style={{
              left: `${region.x}%`,
              top: `${region.y}%`,
              width: `${region.width}%`,
              height: `${region.height}%`,
            }}
          />
        ))}
      </div>
    );
  }

  if (type === "points") {
    return (
      <div className="overlay-layer overlay-point-layer">
        {data.map((point, index) => (
          <div
            key={point.id ?? index}
            className="overlay-point"
            style={{
              left: `${point.x}%`,
              top: `${point.y}%`,
            }}
            title={point.label ?? ""}
          />
        ))}
      </div>
    );
  }

  return null;
}

export default OverlayRenderer;