function Loader({
  size = "md",
  label = "Processing",
  showLabel = true,
  fullscreen = false,
}) {
  const loader = (
    <div
      className={`sq-loader sq-loader-${size}`}
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <span className="sq-loader-spinner" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>

      {showLabel && (
        <span className="sq-loader-label">
          {label}
        </span>
      )}
    </div>
  );

  if (!fullscreen) {
    return loader;
  }

  return (
    <div className="sq-loader-fullscreen">
      {loader}
    </div>
  );
}

export default Loader;