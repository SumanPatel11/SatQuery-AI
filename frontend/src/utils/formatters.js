export function formatNumber(value, decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return Number(value).toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatInteger(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return Number(value).toLocaleString("en-US", {
    maximumFractionDigits: 0,
  });
}

export function formatPercentage(value, decimals = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return `${formatNumber(value, decimals)}%`;
}

export function formatConfidence(value, decimals = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  const normalizedValue = Number(value) <= 1
    ? Number(value) * 100
    : Number(value);

  return formatPercentage(normalizedValue, decimals);
}

export function formatArea(value, unit = "px²", decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return `${formatNumber(value, decimals)} ${unit}`;
}

export function formatDuration(milliseconds) {
  if (
    milliseconds === null ||
    milliseconds === undefined ||
    Number.isNaN(Number(milliseconds))
  ) {
    return "—";
  }

  const totalSeconds = Math.max(Number(milliseconds), 0) / 1000;

  if (totalSeconds < 1) {
    return `${Math.round(totalSeconds * 1000)} ms`;
  }

  if (totalSeconds < 60) {
    return `${formatNumber(totalSeconds, 1)} s`;
  }

  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.round(totalSeconds % 60);

  return `${minutes}m ${seconds}s`;
}

export function formatFileName(fileName, maxLength = 28) {
  if (!fileName) {
    return "Untitled";
  }

  if (fileName.length <= maxLength) {
    return fileName;
  }

  const extensionIndex = fileName.lastIndexOf(".");

  if (extensionIndex <= 0) {
    return `${fileName.slice(0, maxLength - 3)}...`;
  }

  const extension = fileName.slice(extensionIndex);
  const availableLength = Math.max(
    maxLength - extension.length - 3,
    4
  );

  return `${fileName.slice(0, availableLength)}...${extension}`;
}

export function formatDateTime(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "—";
  }

  return date.toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function formatMetricValue(value, unit = "") {
  if (value === null || value === undefined) {
    return "—";
  }

  if (typeof value === "string") {
    return value;
  }

  const formatted = formatNumber(value);

  return unit ? `${formatted} ${unit}` : formatted;
}