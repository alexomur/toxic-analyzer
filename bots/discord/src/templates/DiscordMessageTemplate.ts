import type { MessageMentionOptions } from "discord.js";

export interface DiscordMessageTemplateAuthor {
  name: string;
}

export interface DiscordMessageTemplateEmbedField {
  name: string;
  value: string;
  inline?: boolean;
}

export interface DiscordMessageTemplateEmbed {
  title?: string;
  description?: string;
  color?: number;
  author?: DiscordMessageTemplateAuthor;
  footer?: {
    text: string;
  };
  fields?: DiscordMessageTemplateEmbedField[];
}

export interface DiscordMessageTemplate {
  content?: string;
  embeds?: DiscordMessageTemplateEmbed[];
  attachments?: unknown[];
  allowed_mentions?: MessageMentionOptions;
}
