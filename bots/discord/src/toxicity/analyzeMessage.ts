import type { ToxicityBackendClient } from "./ToxicityBackendClient.js";
import type { ToxicityAnalysisResult } from "./ToxicityAnalysisTypes.js";

export async function analyzeMessage(
  client: ToxicityBackendClient,
  messageText: string
): Promise<ToxicityAnalysisResult> {
  return client.analyze(messageText);
}
