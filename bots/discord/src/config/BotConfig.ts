import type { DiscordMessageTemplate } from "../templates/DiscordMessageTemplate.js";

export interface BotConfig {
  discordToken: string;
  backendBaseUrl: string;
  backendTimeoutMs: number;
  scanChannelIds: string[];
  alertChannelId: string;
  analyzeConcurrency: number;
  logLevel: string;
  alertTemplate: DiscordMessageTemplate;
}

export interface BotConfigFile {
  backendBaseUrl?: unknown;
  backendTimeoutMs?: unknown;
  scanChannelIds?: unknown;
  alertChannelId?: unknown;
  analyzeConcurrency?: unknown;
  alertTemplate?: unknown;
}

export interface BotEnvConfig {
  DISCORD_TOKEN?: string;
  BOT_CONFIG_PATH?: string;
  LOG_LEVEL?: string;
}
