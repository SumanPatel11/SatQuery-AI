import { useCallback, useRef, useState } from "react";

import { useAppContext } from "../context/AppContext";
import { ANALYSIS_STATUS } from "../utils/constants";
import {
  createGeoTiffPreview,
  isGeoTiff,
  isSupportedImage,
} from "../utils/imageUtils";
import api from "../services/api";

function useImageViewer() {
  const {
    setSelectedImage,
    setActiveAnalysis,
    setAnalysisStatus,
    clearError,
    setError,
  } = useAppContext();

  const [image, setImage] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const uploadRequestId = useRef(0);

  const uploadImage = useCallback(
    async (file) => {
      if (!isSupportedImage(file)) return null;

      const requestId = ++uploadRequestId.current;
      const isTiffFile = isGeoTiff(file);

      const imageData = {
        file,
        url: isTiffFile ? null : URL.createObjectURL(file),
        name: file.name,
        type: file.type,
        size: file.size,
        image_id: null,
        uploadStatus: "uploading",
      };

      setImage((currentImage) => {
        if (currentImage?.url?.startsWith("blob:")) {
          URL.revokeObjectURL(currentImage.url);
        }
        return imageData;
      });

      setSelectedImage(imageData);
      setActiveAnalysis(null);
      setAnalysisStatus(ANALYSIS_STATUS.IDLE);
      clearError();

      setIsUploading(true);
      setZoom(1);
      setPosition({ x: 0, y: 0 });
      setIsDragging(false);

      let currentImageData = imageData;

      try {
        if (isTiffFile) {
          const previewUrl = await createGeoTiffPreview(file);

          if (requestId !== uploadRequestId.current) {
            return null;
          }

          currentImageData = {
            ...imageData,
            url: previewUrl,
          };

          setImage(currentImageData);
          setSelectedImage(currentImageData);
        }

        const response = await api.uploadImage(file);

        if (!response?.image_id) {
          throw new Error(
            "Backend upload response did not contain an image ID."
          );
        }

        const uploadedImage = {
          ...currentImageData,
          image_id: response.image_id,
          stored_filename: response.stored_filename,
          uploadStatus: "uploaded",
        };

        if (requestId === uploadRequestId.current) {
          setImage(uploadedImage);
          setSelectedImage(uploadedImage);
          setIsUploading(false);
        }

        return uploadedImage;
      } catch (error) {
        const failedImage = {
          ...currentImageData,
          uploadStatus: "failed",
          uploadError: error.message,
        };

        if (requestId === uploadRequestId.current) {
          setImage(failedImage);
          setSelectedImage(failedImage);
          setIsUploading(false);
          setError(error.message);
        }

        return null;
      }
    },
    [
      setSelectedImage,
      setActiveAnalysis,
      setAnalysisStatus,
      clearError,
      setError,
    ]
  );

  const clearImage = useCallback(() => {
    uploadRequestId.current += 1;

    setImage((currentImage) => {
      if (currentImage?.url?.startsWith("blob:")) {
        URL.revokeObjectURL(currentImage.url);
      }
      return null;
    });

    setSelectedImage(null);
    setActiveAnalysis(null);
    setAnalysisStatus(ANALYSIS_STATUS.IDLE);
    clearError();

    setIsUploading(false);
    setZoom(1);
    setPosition({ x: 0, y: 0 });
    setIsDragging(false);
  }, [
    setSelectedImage,
    setActiveAnalysis,
    setAnalysisStatus,
    clearError,
  ]);

  const zoomIn = useCallback(() => {
    setZoom((currentZoom) =>
      Math.min(Number((currentZoom + 0.25).toFixed(2)), 4)
    );
  }, []);

  const zoomOut = useCallback(() => {
    setZoom((currentZoom) =>
      Math.max(Number((currentZoom - 0.25).toFixed(2)), 1)
    );
  }, []);

  const resetView = useCallback(() => {
    setZoom(1);
    setPosition({ x: 0, y: 0 });
    setIsDragging(false);
  }, []);

  const startPan = useCallback(() => {
    setIsDragging(true);
  }, []);

  const moveImage = useCallback(
    (x, y) => {
      if (!isDragging) return;
      setPosition({ x, y });
    },
    [isDragging]
  );

  const endPan = useCallback(() => {
    setIsDragging(false);
  }, []);

  return {
    image,
    zoom,
    position,
    isDragging,
    isUploading,
    uploadImage,
    clearImage,
    zoomIn,
    zoomOut,
    resetView,
    startPan,
    moveImage,
    endPan,
  };
}

export default useImageViewer;
