import { describe, expect, it } from "vitest";

import { shouldProcessMessage } from "../../src/discord/messageFilters.js";

function createMessage(
  overrides: Partial<{
    author: { id: string; bot: boolean };
    channelId: string;
    content: string;
  }> = {}
) {
  return {
    author: {
      id: "user-1",
      bot: false,
      ...overrides.author
    },
    channelId: overrides.channelId ?? "scan-1",
    content: overrides.content ?? "hello"
  };
}

describe("shouldProcessMessage", () => {
  it("ignores bot messages", () => {
    const result = shouldProcessMessage(
      createMessage({
        author: {
          id: "bot-1",
          bot: true
        }
      }) as never,
      {
        botUserId: "self-bot",
        scanChannelIds: new Set(["scan-1"])
      }
    );

    expect(result).toBe(false);
  });

  it("ignores messages outside scanChannelIds", () => {
    const result = shouldProcessMessage(
      createMessage({
        channelId: "other-channel"
      }) as never,
      {
        botUserId: "self-bot",
        scanChannelIds: new Set(["scan-1"])
      }
    );

    expect(result).toBe(false);
  });

  it("ignores empty messages", () => {
    const result = shouldProcessMessage(
      createMessage({
        content: "   "
      }) as never,
      {
        botUserId: "self-bot",
        scanChannelIds: new Set(["scan-1"])
      }
    );

    expect(result).toBe(false);
  });

  it("allows valid messages from scanChannelIds", () => {
    const result = shouldProcessMessage(createMessage() as never, {
      botUserId: "self-bot",
      scanChannelIds: new Set(["scan-1"])
    });

    expect(result).toBe(true);
  });
});
