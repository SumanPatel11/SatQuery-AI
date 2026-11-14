export const APP_NAME = "SATQUERY AI";

export const APP_VERSION = "0.1";

export const IMAGE_VIEWER = {
  MIN_ZOOM: 1,
  MAX_ZOOM: 4,
  ZOOM_STEP: 0.25,
};

export const SUPPORTED_IMAGE_FORMATS = [
  "JPG",
  "JPEG",
  "PNG",
  "WEBP",
];

export const VIEWER_LAYERS = {
  BASE_IMAGE: "baseImage",
  ANALYSIS: "analysis",
  BUILDINGS: "buildings",
  WATER: "water",
  VEGETATION: "vegetation",
};

export const VIEWER_LAYER_ITEMS = [
  {
    key: VIEWER_LAYERS.BASE_IMAGE,
    label: "Base Image",
    indicatorClass: "base",
  },
  {
    key: VIEWER_LAYERS.ANALYSIS,
    label: "Analysis Overlay",
    indicatorClass: "analysis",
  },
  {
    key: VIEWER_LAYERS.BUILDINGS,
    label: "Buildings",
    indicatorClass: "buildings",
  },
  {
    key: VIEWER_LAYERS.WATER,
    label: "Water",
    indicatorClass: "water",
  },
  {
    key: VIEWER_LAYERS.VEGETATION,
    label: "Vegetation",
    indicatorClass: "vegetation",
  },
];

export const DEFAULT_VIEWER_LAYERS = {
  [VIEWER_LAYERS.BASE_IMAGE]: true,
  [VIEWER_LAYERS.ANALYSIS]: false,
  [VIEWER_LAYERS.BUILDINGS]: false,
  [VIEWER_LAYERS.WATER]: false,
  [VIEWER_LAYERS.VEGETATION]: false,
};

export const OVERLAY_TYPES = {
  BOXES: "boxes",
  REGIONS: "regions",
  POINTS: "points",
};

export const ANALYSIS_STATUS = {
  IDLE: "idle",
  UPLOADING: "uploading",
  PROCESSING: "processing",
  COMPLETED: "completed",
  ERROR: "error",
};

export const RESPONSE_TYPES = {
  DIRECT: "direct",
  SUMMARY: "summary",
  COMPARISON: "comparison",
  CLARIFICATION: "clarification",
  UNSUPPORTED: "unsupported",
};

export const SPATIAL_RELATIONS = {
  LEFT: "left",
  RIGHT: "right",
  TOP: "top",
  BOTTOM: "bottom",
  CENTER: "center",
  QUADRANT: "quadrant",
  NEAR: "near",
};

export const MAX_UPLOAD_SIZE_MB = 50;