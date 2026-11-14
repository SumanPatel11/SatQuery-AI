function ConfidenceBar({
  label = "Confidence",
  value = null,
  showValue = true,
  description = "",
}) {
  const numericValue =
    value === null ||
    value === undefined ||
    value === "" ||
    Number.isNaN(Number(value))
      ? null
      : Math.min(
          Math.max(Number(value), 0),
          1
        );

  const percentage =
    numericValue === null
      ? null
      : numericValue * 100;

  const displayPercentage =
    percentage === null
      ? "—"
      : `${percentage.toFixed(1)}%`;

  return (
    <div className="confidence-bar">
      <div className="confidence-bar-header">
        <div className="confidence-bar-label">
          {label}
        </div>

        {showValue && (
          <div className="confidence-bar-value">
            {displayPercentage}
          </div>
        )}
      </div>

      <div
        className="confidence-bar-track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={
          percentage === null
            ? undefined
            : percentage
        }
        aria-valuetext={
          percentage === null
            ? "Not available"
            : displayPercentage
        }
      >
        <div
          className="confidence-bar-fill"
          style={{
            width:
              percentage === null
                ? "0%"
                : `${percentage}%`,
          }}
        />
      </div>

      {description && (
        <div className="confidence-bar-description">
          {description}
        </div>
      )}
    </div>
  );
}

export default ConfidenceBar;