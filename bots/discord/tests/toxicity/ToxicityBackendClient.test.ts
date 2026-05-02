import { describe, expect, it, vi } from "vitest";

import {
  ToxicityBackendClient,
  ToxicityBackendClientError,
  ToxicityBackendTimeoutError
} from "../../src/toxicity/ToxicityBackendClient.js";

const successPayload = {
  analysisId: "analysis-1",
  label: 1,
  toxicProbability: 0.99982160278796,
  model: {
    modelKey: "baseline_model_v3_3",
    modelVersion: "v3.3"
  },
  reportLevel: "full",
  explanation: {
    calibratedProbability: 0.99982160278796,
    adjustedProbability: 0.99982160278796,
    threshold: 0.39,
    features: [
      {
        name: " туп",
        contribution: 1.245119
      }
    ]
  },
  createdAt: "2026-04-29T10:21:47.9868273+00:00"
};

describe("ToxicityBackendClient", () => {
  it("sends POST /api/v1/toxicity/analyze with reportLevel full", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      void input;
      void init;
      return Promise.resolve(new Response(JSON.stringify(successPayload), {
        status: 200,
        headers: {
          "content-type": "application/json"
        }
      }));
    });
    const fetchImpl = fetchMock as typeof fetch;

    const client = new ToxicityBackendClient({
      baseUrl: "http://localhost:5068",
      timeoutMs: 1000,
      authToken: "bot-token",
      fetchImpl
    });

    await client.analyze("test");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0] as [URL, RequestInit];
    expect(String(url)).toBe("http://localhost:5068/api/v1/toxicity/analyze");
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({
      "content-type": "application/json",
      authorization: "Bearer bot-token"
    });
    expect(JSON.parse(init.body as string)).toEqual({
      text: "test",
      reportLevel: "full"
    });
  });

  it("parses label, toxicProbability, and explanation.features", async () => {
    const client = new ToxicityBackendClient({
      baseUrl: "http://localhost:5068",
      timeoutMs: 1000,
      fetchImpl: vi.fn<typeof fetch>(() => {
        return Promise.resolve(new Response(JSON.stringify(successPayload), {
          status: 200,
          headers: {
            "content-type": "application/json"
          }
        }));
      })
    });

    const result = await client.analyze("test");

    expect(result.label).toBe(1);
    expect(result.toxicProbability).toBe(0.99982160278796);
    expect(result.explanation.features).toEqual([
      {
        name: " туп",
        contribution: 1.245119
      }
    ]);
  });

  it("obtains and reuses a service token when client credentials are configured", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      void init;
      const url = toRequestUrl(input);
      if (url.endsWith("/api/v1/auth/service-token")) {
        return Promise.resolve(new Response(JSON.stringify({
          tokenType: "Bearer",
          accessToken: "issued-token",
          expiresAt: "2099-01-01T00:00:00Z"
        }), {
          status: 200,
          headers: {
            "content-type": "application/json"
          }
        }));
      }

      return Promise.resolve(new Response(JSON.stringify(successPayload), {
        status: 200,
        headers: {
          "content-type": "application/json"
        }
      }));
    });

    const client = new ToxicityBackendClient({
      baseUrl: "http://localhost:5068",
      timeoutMs: 1000,
      serviceClientId: "discord-bot",
      serviceClientSecret: "secret",
      fetchImpl: fetchMock
    });

    await client.analyze("first");
    await client.analyze("second");

    expect(fetchMock).toHaveBeenCalledTimes(3);
    const analyzeCalls = fetchMock.mock.calls.filter(([url]) => toRequestUrl(url).endsWith("/api/v1/toxicity/analyze"));
    expect(analyzeCalls).toHaveLength(2);
    expect(analyzeCalls[0]?.[1]?.headers).toMatchObject({
      authorization: "Bearer issued-token"
    });
  });

  it("handles timeout", async () => {
    const client = new ToxicityBackendClient({
      baseUrl: "http://localhost:5068",
      timeoutMs: 5,
      fetchImpl: vi.fn<typeof fetch>((input, init?: RequestInit) => {
        void input;
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        });
      })
    });

    await expect(client.analyze("test")).rejects.toBeInstanceOf(ToxicityBackendTimeoutError);
  });

  it("handles non-2xx responses", async () => {
    const client = new ToxicityBackendClient({
      baseUrl: "http://localhost:5068",
      timeoutMs: 1000,
      fetchImpl: vi.fn<typeof fetch>(() => {
        return Promise.resolve(new Response(
          JSON.stringify({
            title: "Service Unavailable",
            status: 503
          }),
          {
            status: 503,
            headers: {
              "content-type": "application/json"
            }
          }
        ));
      })
    });

    await expect(client.analyze("test")).rejects.toBeInstanceOf(ToxicityBackendClientError);
  });
});

function toRequestUrl(input: string | URL | Request): string {
  if (typeof input === "string") {
    return input;
  }

  if (input instanceof URL) {
    return input.href;
  }

  return input.url;
}
