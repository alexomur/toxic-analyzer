import type { Client, MessageCreateOptions, TextBasedChannel } from "discord.js";

import type { DiscordMessageTemplate } from "../templates/DiscordMessageTemplate.js";
import type { TemplateContext } from "../templates/TemplateContext.js";
import { renderTemplate } from "../templates/renderTemplate.js";

export class AlertPublisher {
  public constructor(
    private readonly client: Client,
    private readonly alertChannelId: string,
    private readonly template: DiscordMessageTemplate
  ) {}

  public async publish(context: TemplateContext): Promise<void> {
    const channel = await this.client.channels.fetch(this.alertChannelId);

    if (!channel || !isTextBasedChannel(channel)) {
      throw new Error(`Alert channel ${this.alertChannelId} is not a text-based channel.`);
    }

    const rendered = renderTemplate(this.template, context);
    await channel.send(rendered);
  }
}

function isTextBasedChannel(
  channel: Awaited<ReturnType<Client["channels"]["fetch"]>>
): channel is TextBasedChannel & { send: (options: MessageCreateOptions) => Promise<unknown> } {
  return channel !== null && channel.isTextBased() && "send" in channel;
}
