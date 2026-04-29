import type { MessageCreateOptions } from "discord.js";

import type {
  DiscordMessageTemplate,
  DiscordMessageTemplateEmbed
} from "./DiscordMessageTemplate.js";
import type { TemplateContext, TemplatePlaceholder } from "./TemplateContext.js";
import { templatePlaceholders } from "./TemplateContext.js";

const placeholderPattern = /{([a-zA-Z][a-zA-Z0-9]*)}/g;
const templatePlaceholderSet = new Set<string>(templatePlaceholders);
type RenderedEmbed = NonNullable<MessageCreateOptions["embeds"]>[number];

export function renderTemplate(
  template: DiscordMessageTemplate,
  context: TemplateContext
): MessageCreateOptions {
  return {
    content: template.content ? interpolateString(template.content, context) : undefined,
    embeds: template.embeds?.map((embed) => renderEmbed(embed, context)),
    allowedMentions: template.allowed_mentions ?? { parse: [] }
  };
}

function renderEmbed(
  embed: DiscordMessageTemplateEmbed,
  context: TemplateContext
): RenderedEmbed {
  return {
    title: embed.title ? interpolateString(embed.title, context) : undefined,
    description: embed.description ? interpolateString(embed.description, context) : undefined,
    color: embed.color,
    author: embed.author
      ? {
          name: interpolateString(embed.author.name, context)
        }
      : undefined,
    footer: embed.footer
      ? {
          text: interpolateString(embed.footer.text, context)
        }
      : undefined,
    fields: embed.fields?.map((field) => ({
      name: interpolateString(field.name, context),
      value: interpolateString(field.value, context),
      inline: field.inline
    }))
  };
}

function interpolateString(template: string, context: TemplateContext): string {
  return template.replaceAll(placeholderPattern, (placeholder, name: string) => {
    if (isTemplatePlaceholder(name)) {
      return context[name];
    }

    return placeholder;
  });
}

function isTemplatePlaceholder(value: string): value is TemplatePlaceholder {
  return templatePlaceholderSet.has(value);
}
