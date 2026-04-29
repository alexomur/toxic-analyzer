import { z } from "zod";

const messageMentionTypeSchema = z.enum(["everyone", "roles", "users"]);

export const discordMessageTemplateSchema = z
  .object({
    content: z.string().optional(),
    embeds: z
      .array(
        z.object({
          title: z.string().optional(),
          description: z.string().optional(),
          color: z.number().int().min(0).max(0xffffff).optional(),
          author: z
            .object({
              name: z.string()
            })
            .optional(),
          footer: z
            .object({
              text: z.string()
            })
            .optional(),
          fields: z
            .array(
              z.object({
                name: z.string(),
                value: z.string(),
                inline: z.boolean().optional()
              })
            )
            .optional()
        })
      )
      .optional(),
    attachments: z
      .array(z.unknown())
      .optional()
      .refine(
        (value) => value === undefined || value.length === 0,
        "Non-empty attachments are unsupported in MVP."
      ),
    allowed_mentions: z
      .object({
        parse: z.array(messageMentionTypeSchema)
      })
      .optional()
  })
  .refine(
    (value) => Boolean(value.content) || Boolean(value.embeds?.length),
    "Template must define content or at least one embed."
  );
