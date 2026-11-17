import api from "./api";

export async function analyzeImage({
  image,
  second_image = null,
  query = "",
  analysisType = null,
  options = {},
}) {
  if (!image) {
    throw new Error("An image is required for analysis.");
  }

  return api.runAnalysis({
    image,
    second_image,
    query,
    analysisType,
    options,
  });
}

export async function getAnalysis(analysisId) {
  if (!analysisId) {
    throw new Error("Analysis ID is required.");
  }

  return api.getAnalysisResult(analysisId);
}

export async function getAnalysisHistory() {
  return api.getAnalysisHistory();
}

export async function checkAnalysisService() {
  return api.getHealth();
}

export default {
  analyzeImage,
  getAnalysis,
  getAnalysisHistory,
  checkAnalysisService,
};
