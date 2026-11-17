import test from "node:test";
import assert from "node:assert/strict";
import {
  getAnalysisErrorMessage,
  getAnalysisSummaryItems,
  getAssistantResponse,
  getVegetationPresentation,
} from "../src/utils/analysisSummary.js";

test("assistant summary prefers the backend conversational response", () => {
  assert.equal(
    getAssistantResponse({ assistant_response: "I found 19 buildings." }),
    "I found 19 buildings.",
  );
  assert.match(getAssistantResponse({}), /without a conversational summary/);
});

test("building summary reads only backend count and detection fields", () => {
  const [item] = getAnalysisSummaryItems({
    execution: { results: [{
      task: "BUILDING_DETECTION",
      result: {
        building_count: 2,
        detections: [{ class_id: 0, confidence: 0.81, bbox_xyxy: [1, 2, 3, 4] }],
        model: "YOLO26n SpaceNet2",
        device: "cpu",
      },
    }] },
  });

  assert.equal(item.buildingCount, 2);
  assert.equal(item.detections.length, 1);
  assert.equal(item.detections[0].confidence, 0.81);
  assert.equal(item.model, "YOLO26n SpaceNet2");
});

test("land-cover summary preserves class pixel counts", () => {
  const counts = { background: 12, building: 4 };
  const [item] = getAnalysisSummaryItems({
    execution: { results: [{ task: "LAND_COVER_DETECTION", result: { class_pixel_counts: counts } }] },
  });

  assert.deepEqual(item.classPixelCounts, counts);
});

test("change summary uses model-resolution pixel fields", () => {
  const [item] = getAnalysisSummaryItems({
    execution: { results: [{ task: "BUILDING_CHANGE", result: {
      changed_pixels_at_model_resolution: 7,
      changed_fraction_at_model_resolution: 0.25,
    } }] },
  });

  assert.equal(item.changedPixels, 7);
  assert.equal(item.changedFraction, 0.25);
});

test("flood summary preserves valid, invalid, flood, and fraction fields", () => {
  const [item] = getAnalysisSummaryItems({
    execution: { results: [{ task: "FLOODED_AREA_DETECTION", result: {
      valid_pixels: 10,
      invalid_pixels: 5,
      flood_pixels: 3,
      flood_area_pixel_fraction: 0.3,
    } }] },
  });

  assert.equal(item.validPixels, 10);
  assert.equal(item.invalidPixels, 5);
  assert.equal(item.floodPixels, 3);
  assert.equal(item.floodPixelFraction, 0.3);
});

test("missing backend values remain missing", () => {
  const [item] = getAnalysisSummaryItems({ execution: { results: [{ task: "BUILDING_DETECTION", result: {} }] } });

  assert.equal(item.buildingCount, undefined);
  assert.deepEqual(item.detections, []);
  assert.equal(item.changedPixels, undefined);
  assert.equal(item.floodPixels, undefined);
});

test("vegetation percentage presentation uses backend pixel statistics", () => {
  const analysis = {
    query: "What percentage of this image contains vegetation?",
    execution: { results: [{ task: "LAND_COVER_DETECTION", result: {
      model: "LoveDA MobileNetV3 Small U-Net",
      class_pixel_counts: { forest: 120, agriculture: 80 },
      vegetation_pixel_summary: {
        forest_pixels: 120,
        agriculture_pixels: 80,
        total_vegetation_pixels: 200,
        valid_image_pixels: 1000,
        vegetation_pixel_percentage: 20,
      },
    } }] },
  };
  const [item] = getAnalysisSummaryItems(analysis);
  const presentation = getVegetationPresentation(analysis, item);
  assert.deepEqual(presentation, {
    forestPixels: 120,
    agriculturePixels: 80,
    totalVegetationPixels: undefined,
    vegetationPixelPercentage: 20,
  });
});

test("how much vegetation presentation includes actual class and total pixel counts", () => {
  const analysis = {
    query: "How much vegetation is present?",
    execution: { results: [{ task: "LAND_COVER_DETECTION", result: {
      class_pixel_counts: { forest: 120, agriculture: 80 },
    } }] },
  };
  const [item] = getAnalysisSummaryItems(analysis);
  assert.deepEqual(getVegetationPresentation(analysis, item), {
    forestPixels: 120,
    agriculturePixels: 80,
    totalVegetationPixels: 200,
    vegetationPixelPercentage: undefined,
  });
});

test("class-specific pixel count does not imply a combined vegetation total", () => {
  const analysis = {
    query: "Report forest pixel count.",
    execution: { results: [{ task: "LAND_COVER_DETECTION", result: {
      class_pixel_counts: { forest: 12, agriculture: 9 },
    } }] },
  };
  const [item] = getAnalysisSummaryItems(analysis);
  const presentation = getVegetationPresentation(analysis, item);
  assert.equal(presentation.forestPixels, 12);
  assert.equal(presentation.totalVegetationPixels, undefined);
});

test("pixel percentage fallback requires class totals to match image dimensions", () => {
  const base = {
    query: "What percentage of the image contains vegetation?",
    execution: { results: [{ task: "LAND_COVER_DETECTION", result: {
      image_width: 2,
      image_height: 2,
      class_pixel_counts: { background: 1, forest: 2, agriculture: 1 },
    } }] },
  };
  const [item] = getAnalysisSummaryItems(base);
  assert.equal(getVegetationPresentation(base, item).vegetationPixelPercentage, 75);

  const inconsistent = structuredClone(base);
  inconsistent.execution.results[0].result.image_width = 3;
  const [inconsistentItem] = getAnalysisSummaryItems(inconsistent);
  assert.equal(
    getVegetationPresentation(inconsistent, inconsistentItem).vegetationPixelPercentage,
    undefined,
  );
});

test("frontend exposes the actual safe capability validation reason", () => {
  assert.equal(getAnalysisErrorMessage({
    execution: { validation: { tasks: [{
      execution_status: "BLOCKED",
      reason: "Geographic or physical land-cover area is not supported.",
    }] } },
  }), "Geographic or physical land-cover area is not supported.");
});
