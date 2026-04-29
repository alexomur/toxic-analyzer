import { describe, expect, it } from "vitest";

import { renderTemplate } from "../../src/templates/renderTemplate.js";
import type { TemplateContext } from "../../src/templates/TemplateContext.js";

const context: TemplateContext = {
  messageText: "hello",
  messageUrl: "https://discord.com/channels/1/2/3",
  messageId: "3",
  channelId: "2",
  channelMention: "<#2>",
  guildId: "1",
  authorId: "42",
  authorUsername: "user",
  authorTag: "user#0001",
  authorMention: "<@42>",
  label: "1",
  toxicProbability: "0.99",
  analysisId: "analysis-1",
  modelKey: "baseline_model_v3_3",
  modelVersion: "v3.3",
  reportLevel: "full",
  createdAt: "2026-04-29T10:21:47.9868273+00:00",
  calibratedProbability: "0.98",
  adjustedProbability: "0.97",
  threshold: "0.39",
  features: "1. туп: 1.245119\n2. груб: 0.5",
  featuresJson: '[{"name":" туп","contribution":1.245119}]'
};

describe("renderTemplate", () => {
  it("replaces message, label, and probability placeholders", () => {
    const rendered = renderTemplate(
      {
        content: "{messageText} {label} {toxicProbability}"
      },
      context
    );

    expect(rendered.content).toBe("hello 1 0.99");
  });

  it("replaces author, channel, and message placeholders", () => {
    const rendered = renderTemplate(
      {
        content: "{authorTag} {authorMention} {channelMention} {messageUrl}"
      },
      context
    );

    expect(rendered.content).toBe(
      "user#0001 <@42> <#2> https://discord.com/channels/1/2/3"
    );
  });

  it("formats all features in features placeholder", () => {
    const rendered = renderTemplate(
      {
        content: "{features}"
      },
      context
    );

    expect(rendered.content).toContain("1. туп: 1.245119");
    expect(rendered.content).toContain("2. груб: 0.5");
  });

  it("formats all features in featuresJson placeholder", () => {
    const rendered = renderTemplate(
      {
        content: "{featuresJson}"
      },
      context
    );

    expect(rendered.content).toBe('[{"name":" туп","contribution":1.245119}]');
  });

  it("does not execute arbitrary code", () => {
    const rendered = renderTemplate(
      {
        content: "{constructor.constructor('return process')()}"
      },
      context
    );

    expect(rendered.content).toBe("{constructor.constructor('return process')()}");
  });

  it("keeps unknown placeholders unchanged", () => {
    const rendered = renderTemplate(
      {
        content: "{unknownPlaceholder}"
      },
      context
    );

    expect(rendered.content).toBe("{unknownPlaceholder}");
  });
});
