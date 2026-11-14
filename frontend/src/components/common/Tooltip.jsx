import { useState } from "react";

function Tooltip({
  children,
  content,
  position = "top",
  delay = 180,
  disabled = false,
}) {
  const [visible, setVisible] = useState(false);

  if (disabled || !content) {
    return children;
  }

  const showTooltip = () => {
    setVisible(true);
  };

  const hideTooltip = () => {
    setVisible(false);
  };

  return (
    <span
      className={`sq-tooltip-wrapper sq-tooltip-${position}`}
      onMouseEnter={showTooltip}
      onMouseLeave={hideTooltip}
      onFocus={showTooltip}
      onBlur={hideTooltip}
      style={{
        "--tooltip-delay": `${delay}ms`,
      }}
    >
      {children}

      <span
        className={`sq-tooltip ${visible ? "is-visible" : ""}`}
        role="tooltip"
      >
        {content}
      </span>
    </span>
  );
}

export default Tooltip;