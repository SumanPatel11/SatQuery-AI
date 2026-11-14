import {
  ArrowDownRight,
  ArrowUpRight,
  Minus,
} from "lucide-react";

function MetricCard({
  label,
  value = "—",
  unit = "",
  icon: Icon = null,
  trend = null,
  trendLabel = "",
  description = "",
  status = "neutral",
}) {
  const displayValue =
    value === null || value === undefined || value === ""
      ? "—"
      : value;

  const getTrendIcon = () => {
    if (trend === "up") {
      return (
        <ArrowUpRight
          size={12}
          strokeWidth={1.8}
        />
      );
    }

    if (trend === "down") {
      return (
        <ArrowDownRight
          size={12}
          strokeWidth={1.8}
        />
      );
    }

    return (
      <Minus
        size={11}
        strokeWidth={1.8}
      />
    );
  };

  return (
    <article
      className={`metric-card metric-card-${status}`}
    >
      <div className="metric-card-top">
        <div className="metric-card-label">
          {label}
        </div>

        {Icon && (
          <div className="metric-card-icon">
            <Icon
              size={15}
              strokeWidth={1.7}
            />
          </div>
        )}
      </div>

      <div className="metric-card-value-row">
        <span className="metric-card-value">
          {displayValue}
        </span>

        {unit && displayValue !== "—" && (
          <span className="metric-card-unit">
            {unit}
          </span>
        )}
      </div>

      {(trend || trendLabel) && (
        <div
          className={`metric-card-trend ${
            trend ? `trend-${trend}` : ""
          }`}
        >
          {trend && getTrendIcon()}

          {trendLabel && (
            <span>{trendLabel}</span>
          )}
        </div>
      )}

      {description && (
        <div className="metric-card-description">
          {description}
        </div>
      )}
    </article>
  );
}

export default MetricCard;