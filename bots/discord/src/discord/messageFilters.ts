import type { Message } from "discord.js";

export interface MessageFilterOptions {
  botUserId: string;
  scanChannelIds: ReadonlySet<string>;
}

export function shouldProcessMessage(
  message: Message,
  options: MessageFilterOptions
): boolean {
  if (message.author.bot) {
    return false;
  }

  if (message.author.id === options.botUserId) {
    return false;
  }

  if (!options.scanChannelIds.has(message.channelId)) {
    return false;
  }

  if (message.content.trim().length === 0) {
    return false;
  }

  return true;
}
