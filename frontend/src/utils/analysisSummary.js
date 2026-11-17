export function getAnalysisSummaryItems(analysis) {
  const results = Array.isArray(analysis?.execution?.results)
    ? analysis.execution.results
    : [];

  return results.map((item) => {
    const result = item?.result || {};
    return {
      task: item?.task || result.capability || "Analysis",
      model: result.model,
      device: result.device,
      imageWidth: result.image_width,
      imageHeight: result.image_height,
      buildingCount: result.building_count,
      detections: Array.isArray(result.detections) ? result.detections : [],
      classPixelCounts: result.class_pixel_counts,
      vegetationPixelSummary: result.vegetation_pixel_summary,
      changedPixels: result.changed_pixels_at_model_resolution,
      changedFraction: result.changed_fraction_at_model_resolution,
      floodPixels: result.flood_pixels,
      validPixels: result.valid_pixels,
      invalidPixels: result.invalid_pixels,
      floodPixelFraction: result.flood_area_pixel_fraction,
      error: item?.error,
    };
  });
}

export function getAssistantResponse(analysis) {
  const answer = analysis?.assistant_response;
  return typeof answer === "string" && answer.trim()
    ? answer.trim()
    : "The backend returned an analysis without a conversational summary.";
}

export function getVegetationPresentation(analysis, item) {
  const query = String(analysis?.query || "").toLowerCase();
  const isLandCover = item?.task === "LAND_COVER_DETECTION";
  const isVegetationQuery = /\b(vegetation|forest|agricultur\w*)\b/.test(query);
  if (!isLandCover || !isVegetationQuery) return null;

  const counts = item.classPixelCounts || {};
  const summary = item.vegetationPixelSummary || {};
  const forestPixels = summary.forest_pixels ?? counts.forest;
  const agriculturePixels = summary.agriculture_pixels ?? counts.agriculture;
  const canDeriveTotal = Number.isInteger(forestPixels) && forestPixels >= 0
    && Number.isInteger(agriculturePixels) && agriculturePixels >= 0;
  const totalVegetationPixels = summary.total_vegetation_pixels
    ?? (canDeriveTotal ? forestPixels + agriculturePixels : undefined);
  const classSpecificQuery = /\b(forest|forests|agricultur\w*)\b/.test(query);
  const totalRequested = /\b(how\s+much|total|coverage|covered)\b/.test(query)
    || (!classSpecificQuery
      && /\bvegetation\b/.test(query)
      && /\b(pixel\s+counts?|counts?)\b/.test(query));
  const percentageRequested = /\b(percent(?:age)?|fraction|coverage|covered)\b/.test(query);
  const classPixelTotal = Object.values(counts).every(
    (value) => Number.isInteger(value) && value >= 0,
  )
    ? Object.values(counts).reduce((sum, value) => sum + value, 0)
    : undefined;
  const dimensionsMatchCounts = Number.isInteger(item.imageWidth)
    && item.imageWidth > 0
    && Number.isInteger(item.imageHeight)
    && item.imageHeight > 0
    && classPixelTotal === item.imageWidth * item.imageHeight;
  const validImagePixels = summary.valid_image_pixels
    ?? (dimensionsMatchCounts ? classPixelTotal : undefined);
  const vegetationPixelPercentage = summary.vegetation_pixel_percentage
    ?? (Number.isInteger(totalVegetationPixels) && totalVegetationPixels >= 0
      && Number.isInteger(validImagePixels) && validImagePixels > 0
      ? (totalVegetationPixels / validImagePixels) * 100
      : undefined);

  return {
    forestPixels,
    agriculturePixels,
    totalVegetationPixels: totalRequested ? totalVegetationPixels : undefined,
    vegetationPixelPercentage: percentageRequested ? vegetationPixelPercentage : undefined,
  };
}

export function getAnalysisErrorMessage(result) {
  const taskError = result?.execution?.results?.find((item) => item?.error)?.error;
  const validation = result?.execution?.validation;
  const validationTaskError = validation?.tasks?.find(
    (task) => task?.execution_status === "BLOCKED" && task?.reason,
  )?.reason;
  const nlpValidationTaskError = result?.nlp?.capability_validation?.tasks?.find(
    (task) => task?.execution_status === "BLOCKED" && task?.reason,
  )?.reason;
  return taskError || validation?.reason || validationTaskError || nlpValidationTaskError;
}
