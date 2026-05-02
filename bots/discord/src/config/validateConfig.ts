import { z } from "zod";

import type { BotConfig } from "./BotConfig.js";
import { discordMessageTemplateSchema } from "../templates/validateTemplate.js";

const configSchema = z.object({
  discordToken: z.string().trim().min(1, "discordToken is required."),
  backendBaseUrl: z.url("backendBaseUrl must be a valid URL."),
  backendTimeoutMs: z.number().int().positive().max(60000).default(10000),
  backendAuthToken: z.string().trim().min(1).optional(),
  backendServiceClientId: z.string().trim().min(1).optional(),
  backendServiceClientSecret: z.string().trim().min(1).optional(),
  scanChannelIds: z
    .array(z.string().trim().min(1))
    .min(1, "scanChannelIds must contain at least one channel ID."),
  alertChannelId: z.string().trim().min(1, "alertChannelId is required."),
  analyzeConcurrency: z.number().int().positive().max(32).default(4),
  logLevel: z.string().trim().min(1).default("info"),
  alertTemplate: discordMessageTemplateSchema
}).superRefine((config, context) => {
  const hasServiceClientId = config.backendServiceClientId !== undefined;
  const hasServiceClientSecret = config.backendServiceClientSecret !== undefined;

  if (hasServiceClientId !== hasServiceClientSecret) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: hasServiceClientId ? ["backendServiceClientSecret"] : ["backendServiceClientId"],
      message: "backendServiceClientId and backendServiceClientSecret must be configured together."
    });
  }
});

export function validateConfig(input: unknown): BotConfig {
  return configSchema.parse(input);
}
