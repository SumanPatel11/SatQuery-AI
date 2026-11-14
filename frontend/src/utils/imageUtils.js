import { fromBlob } from "geotiff";

const SUPPORTED_IMAGE_TYPES = [
  "image/jpeg",
  "image/jpg",
  "image/png",
  "image/webp",
  "image/tiff",
];

const SUPPORTED_EXTENSIONS = [
  "jpg",
  "jpeg",
  "png",
  "webp",
  "tif",
  "tiff",
];

export function formatFileSize(bytes) {
  if (!bytes || bytes <= 0) return "0 B";

  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1
  );

  const size = bytes / Math.pow(1024, index);
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export function getImageFormat(file) {
  if (!file) return "Unknown";

  if (file.type) {
    const parts = file.type.split("/");
    if (parts.length === 2) return parts[1].toUpperCase();
  }

  const extension = file.name?.split(".").pop();
  return extension ? extension.toUpperCase() : "Unknown";
}

export function getFileExtension(file) {
  if (!file?.name) return "";

  const parts = file.name.split(".");
  return parts.length < 2 ? "" : parts.pop().toLowerCase();
}

export function isGeoTiff(file) {
  return ["tif", "tiff"].includes(getFileExtension(file));
}

export function isSupportedImage(file) {
  if (!file) return false;

  if (SUPPORTED_IMAGE_TYPES.includes(file.type)) return true;

  return SUPPORTED_EXTENSIONS.includes(getFileExtension(file));
}

export async function createGeoTiffPreview(file) {
  const tiff = await fromBlob(file);
  const image = await tiff.getImage();

  const width = image.getWidth();
  const height = image.getHeight();

  const rasters = await image.readRasters({
    samples: [0],
  });

  const raster = rasters[0];
  const validValues = [];

  for (let i = 0; i < raster.length; i++) {
    if (Number.isFinite(raster[i])) {
      validValues.push(raster[i]);
    }
  }

  if (validValues.length === 0) {
    throw new Error("GeoTIFF contains no valid pixels for preview.");
  }

  validValues.sort((a, b) => a - b);

  const percentile = (p) =>
    validValues[Math.floor((validValues.length - 1) * p)];

  const low = percentile(0.02);
  const high = percentile(0.98);

  if (high <= low) {
    throw new Error("GeoTIFF pixel range is unsuitable for preview.");
  }

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;

  const context = canvas.getContext("2d");

  if (!context) {
    throw new Error("Unable to create GeoTIFF preview canvas.");
  }

  const imageData = context.createImageData(width, height);

  for (let i = 0; i < raster.length; i++) {
    const offset = i * 4;
    const value = raster[i];

    const gray = Number.isFinite(value)
      ? Math.round(
          Math.max(0, Math.min(1, (value - low) / (high - low))) * 255
        )
      : 0;

    imageData.data[offset] = gray;
    imageData.data[offset + 1] = gray;
    imageData.data[offset + 2] = gray;
    imageData.data[offset + 3] = 255;
  }

  context.putImageData(imageData, 0, 0);

  return canvas.toDataURL("image/png");
}

export function getImageMetadata(file) {
  if (!file) return null;

  return {
    name: file.name,
    type: file.type,
    format: getImageFormat(file),
    extension: getFileExtension(file),
    size: file.size,
    formattedSize: formatFileSize(file.size),
  };
}

export function getImageDimensions(file) {
  return new Promise((resolve, reject) => {
    if (!file) {
      reject(new Error("No image file provided."));
      return;
    }

    const imageUrl = URL.createObjectURL(file);
    const image = new Image();

    image.onload = () => {
      const dimensions = {
        width: image.naturalWidth,
        height: image.naturalHeight,
        aspectRatio: image.naturalWidth / image.naturalHeight,
      };

      URL.revokeObjectURL(imageUrl);
      resolve(dimensions);
    };

    image.onerror = () => {
      URL.revokeObjectURL(imageUrl);
      reject(new Error("Unable to read image dimensions."));
    };

    image.src = imageUrl;
  });
}
