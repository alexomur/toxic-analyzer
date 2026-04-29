import { describe, expect, it } from "vitest";
import { ZodError } from "zod";

import { validateConfig } from "../../src/config/validateConfig.js";

const validConfig = {
  discordToken: "token",
  backendBaseUrl: "http://localhost:5068",
  backendTimeoutMs: 10000,
  scanChannelIds: ["123"],
  alertChannelId: "456",
  analyzeConcurrency: 4,
  logLevel: "info",
  alertTemplate: {
    content: "Alert {messageText}",
    attachments: []
  }
};

describe("validateConfig", () => {
  it("fails when discordToken is missing", () => {
    expect(() => validateConfig({ ...validConfig, discordToken: "" })).toThrow(ZodError);
  });

  it("fails when scanChannelIds is empty", () => {
    expect(() => validateConfig({ ...validConfig, scanChannelIds: [] })).toThrow(ZodError);
  });

  it("fails when alertChannelId is missing", () => {
    expect(() => validateConfig({ ...validConfig, alertChannelId: "" })).toThrow(ZodError);
  });

  it("fails when backendBaseUrl is missing", () => {
    expect(() => validateConfig({ ...validConfig, backendBaseUrl: "" })).toThrow(ZodError);
  });

  it("rejects non-empty attachments in the template", () => {
    expect(() =>
      validateConfig({
        ...validConfig,
        alertTemplate: {
          content: "Alert",
          attachments: [{ id: "1" }]
        }
      })
    ).toThrow("Non-empty attachments are unsupported in MVP.");
  });
});
