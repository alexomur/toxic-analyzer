import type { ToxicityAnalysisResult } from "../toxicity/ToxicityAnalysisTypes.js";

export function shouldSendAlert(analysis: ToxicityAnalysisResult): boolean {
  return analysis.label === 1;
}
