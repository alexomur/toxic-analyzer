import { config as loadDotEnv } from "dotenv";
import { readFile } from "node:fs/promises";
import path from "node:path";

import type { BotConfig, BotConfigFile, BotEnvConfig } from "./BotConfig.js";
import { validateConfig } from "./validateConfig.js";

export async function loadConfig(): Promise<BotConfig> {
  loadDotEnv();

  const env = process.env as BotEnvConfig;
  const configPath = path.resolve(process.cwd(), env.BOT_CONFIG_PATH ?? "./config.json");
  const fileContent = await readFile(configPath, "utf8");
  const fileConfig = JSON.parse(fileContent) as BotConfigFile;

  return validateConfig({
    discordToken: env.DISCORD_TOKEN,
    backendAuthToken: env.BACKEND_AUTH_TOKEN,
    backendServiceClientId: env.BACKEND_SERVICE_CLIENT_ID,
    backendServiceClientSecret: env.BACKEND_SERVICE_CLIENT_SECRET,
    logLevel: env.LOG_LEVEL,
    ...fileConfig
  });
}
