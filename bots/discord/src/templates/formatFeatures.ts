import type { ToxicityFeature } from "../toxicity/ToxicityAnalysisTypes.js";

export function formatFeatures(features: ToxicityFeature[]): string {
  if (features.length === 0) {
    return "No features returned.";
  }

  return features
    .map((feature, index) => `${index + 1}. ${feature.name}: ${feature.contribution}`)
    .join("\n");
}
