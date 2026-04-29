import type { Client, Message } from "discord.js";
import type { Logger } from "pino";

import type { BotConfig } from "../config/BotConfig.js";
import { createConcurrencyLimiter } from "../runtime/concurrency.js";
import type { ToxicityBackendClient } from "../toxicity/ToxicityBackendClient.js";
import { shouldSendAlert } from "./alertDecision.js";
import type { AlertPublisher } from "./alertPublisher.js";
import { createTemplateContext } from "./messageContext.js";
import { shouldProcessMessage } from "./messageFilters.js";

export class DiscordBot {
  private readonly scanChannelIds: ReadonlySet<string>;
  private readonly runWithLimit: <T>(operation: () => Promise<T>) => Promise<T>;

  public constructor(
    private readonly client: Client,
    private readonly config: BotConfig,
    private readonly toxicityClient: ToxicityBackendClient,
    private readonly alertPublisher: AlertPublisher,
    private readonly logger: Logger
  ) {
    this.scanChannelIds = new Set(config.scanChannelIds);
    this.runWithLimit = createConcurrencyLimiter(config.analyzeConcurrency);
  }

  public async start(): Promise<void> {
    this.client.once("ready", () => {
      this.logger.info(
        {
          botUserId: this.client.user?.id,
          scanChannelCount: this.config.scanChannelIds.length,
          alertChannelId: this.config.alertChannelId
        },
        "Discord bot connected."
      );
    });

    this.client.on("messageCreate", (message) => {
      void this.runWithLimit(() => this.handleMessageCreate(message)).catch((error: unknown) => {
        this.logger.error({ error }, "Unhandled message processing error.");
      });
    });

    await this.client.login(this.config.discordToken);
  }

  public stop(): Promise<void> {
    return this.client.destroy();
  }

  public async handleMessageCreate(message: Message): Promise<void> {
    const botUserId = this.client.user?.id;

    if (!botUserId) {
      this.logger.warn({ messageId: message.id }, "Client user is not ready yet.");
      return;
    }

    if (
      !shouldProcessMessage(message, {
        botUserId,
        scanChannelIds: this.scanChannelIds
      })
    ) {
      return;
    }

    try {
      const analysis = await this.toxicityClient.analyze(message.content);

      if (!shouldSendAlert(analysis)) {
        return;
      }

      const templateContext = createTemplateContext(message, analysis);
      await this.alertPublisher.publish(templateContext);
    } catch (error: unknown) {
      this.logger.error(
        {
          error,
          messageId: message.id,
          channelId: message.channelId,
          guildId: message.guildId ?? null
        },
        "Failed to process Discord message."
      );
    }
  }
}
