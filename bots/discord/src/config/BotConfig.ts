import type { DiscordMessageTemplate } from "../templates/DiscordMessageTemplate.js";

export interface BotConfig {
  discordToken: string;
  backendBaseUrl: string;
  backendTimeoutMs: number;
  backendAuthToken?: string;
  backendServiceClientId?: string;
  backendServiceClientSecret?: string;
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
  BACKEND_AUTH_TOKEN?: string;
  BACKEND_SERVICE_CLIENT_ID?: string;
  BACKEND_SERVICE_CLIENT_SECRET?: string;
  LOG_LEVEL?: string;
}
