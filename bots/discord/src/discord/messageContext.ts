import type { Message } from "discord.js";

import type { TemplateContext } from "../templates/TemplateContext.js";
import { formatFeatures } from "../templates/formatFeatures.js";
import type { ToxicityAnalysisResult } from "../toxicity/ToxicityAnalysisTypes.js";

export function createTemplateContext(
  message: Message,
  analysis: ToxicityAnalysisResult
): TemplateContext {
  return {
    messageText: message.content,
    messageUrl: message.url,
    messageId: message.id,
    channelId: message.channelId,
    channelMention: `<#${message.channelId}>`,
    guildId: message.guildId ?? "",
    authorId: message.author.id,
    authorUsername: message.author.username,
    authorTag: message.author.tag,
    authorMention: `<@${message.author.id}>`,
    label: String(analysis.label),
    toxicProbability: String(analysis.toxicProbability),
    analysisId: analysis.analysisId,
    modelKey: analysis.model.modelKey,
    modelVersion: analysis.model.modelVersion,
    reportLevel: analysis.reportLevel,
    createdAt: analysis.createdAt,
    calibratedProbability: String(analysis.explanation.calibratedProbability),
    adjustedProbability: String(analysis.explanation.adjustedProbability),
    threshold: String(analysis.explanation.threshold),
    features: formatFeatures(analysis.explanation.features),
    featuresJson: JSON.stringify(analysis.explanation.features)
  };
}
