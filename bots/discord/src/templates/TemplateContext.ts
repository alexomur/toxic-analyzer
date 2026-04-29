export interface TemplateContext {
  messageText: string;
  messageUrl: string;
  messageId: string;
  channelId: string;
  channelMention: string;
  guildId: string;
  authorId: string;
  authorUsername: string;
  authorTag: string;
  authorMention: string;
  label: string;
  toxicProbability: string;
  analysisId: string;
  modelKey: string;
  modelVersion: string;
  reportLevel: string;
  createdAt: string;
  calibratedProbability: string;
  adjustedProbability: string;
  threshold: string;
  features: string;
  featuresJson: string;
}

export type TemplatePlaceholder = keyof TemplateContext;

export const templatePlaceholders = [
  "messageText",
  "messageUrl",
  "messageId",
  "channelId",
  "channelMention",
  "guildId",
  "authorId",
  "authorUsername",
  "authorTag",
  "authorMention",
  "label",
  "toxicProbability",
  "analysisId",
  "modelKey",
  "modelVersion",
  "reportLevel",
  "createdAt",
  "calibratedProbability",
  "adjustedProbability",
  "threshold",
  "features",
  "featuresJson"
] as const satisfies readonly TemplatePlaceholder[];
