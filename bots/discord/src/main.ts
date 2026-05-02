import { loadConfig } from "./config/loadConfig.js";
import { AlertPublisher } from "./discord/alertPublisher.js";
import { createDiscordClient } from "./discord/createDiscordClient.js";
import { DiscordBot } from "./discord/DiscordBot.js";
import { createLogger } from "./runtime/logger.js";
import { registerGracefulShutdown } from "./runtime/shutdown.js";
import { ToxicityBackendClient } from "./toxicity/ToxicityBackendClient.js";

async function main(): Promise<void> {
  const config = await loadConfig();
  const logger = createLogger(config.logLevel);
  const discordClient = createDiscordClient();
  const toxicityClient = new ToxicityBackendClient({
    baseUrl: config.backendBaseUrl,
    timeoutMs: config.backendTimeoutMs,
    authToken: config.backendAuthToken,
    serviceClientId: config.backendServiceClientId,
    serviceClientSecret: config.backendServiceClientSecret
  });
  const alertPublisher = new AlertPublisher(
    discordClient,
    config.alertChannelId,
    config.alertTemplate
  );
  const bot = new DiscordBot(discordClient, config, toxicityClient, alertPublisher, logger);

  registerGracefulShutdown(async () => {
    await bot.stop();
  }, logger);

  await bot.start();
}

void main();
