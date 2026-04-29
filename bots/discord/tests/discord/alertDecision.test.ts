import { describe, expect, it, vi } from "vitest";

import type { BotConfig } from "../../src/config/BotConfig.js";
import { DiscordBot } from "../../src/discord/DiscordBot.js";
import type { ToxicityAnalysisResult } from "../../src/toxicity/ToxicityAnalysisTypes.js";

const baseConfig: BotConfig = {
  discordToken: "token",
  backendBaseUrl: "http://localhost:5068",
  backendTimeoutMs: 10000,
  scanChannelIds: ["scan-1"],
  alertChannelId: "alert-1",
  analyzeConcurrency: 2,
  logLevel: "info",
  alertTemplate: {
    content: "Alert {messageText}",
    attachments: []
  }
};

const toxicAnalysis: ToxicityAnalysisResult = {
  analysisId: "analysis-1",
  label: 1,
  toxicProbability: 0.9,
  model: {
    modelKey: "baseline_model_v3_3",
    modelVersion: "v3.3"
  },
  reportLevel: "full",
  explanation: {
    calibratedProbability: 0.9,
    adjustedProbability: 0.9,
    threshold: 0.39,
    features: [
      {
        name: "туп",
        contribution: 1.2
      }
    ]
  },
  createdAt: "2026-04-29T10:21:47.9868273+00:00"
};

function createBot(label: 0 | 1) {
  const client = {
    user: {
      id: "bot-1"
    },
    once: vi.fn(),
    on: vi.fn(),
    login: vi.fn(() => Promise.resolve("token")),
    destroy: vi.fn()
  };

  const toxicityClient = {
    analyze: vi.fn(() => Promise.resolve({
      ...toxicAnalysis,
      label
    }))
  };

  const alertPublisher = {
    publish: vi.fn(() => Promise.resolve(undefined))
  };

  const logger = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn()
  };

  const bot = new DiscordBot(
    client as never,
    baseConfig,
    toxicityClient as never,
    alertPublisher as never,
    logger as never
  );

  const message = {
    id: "message-1",
    content: "bad text",
    url: "https://discord.com/channels/1/scan-1/message-1",
    channelId: "scan-1",
    guildId: "guild-1",
    author: {
      id: "user-1",
      bot: false,
      username: "user",
      tag: "user#0001"
    }
  };

  return {
    bot,
    alertPublisher,
    message
  };
}

describe("DiscordBot alert decision", () => {
  it("label=1 sends an alert", async () => {
    const { bot, alertPublisher, message } = createBot(1);

    await bot.handleMessageCreate(message as never);

    expect(alertPublisher.publish).toHaveBeenCalledOnce();
  });

  it("label=0 does not send an alert", async () => {
    const { bot, alertPublisher, message } = createBot(0);

    await bot.handleMessageCreate(message as never);

    expect(alertPublisher.publish).not.toHaveBeenCalled();
  });
});
