import {
  toxicityAnalysisResultSchema,
  type ProblemDetailsError,
  type ToxicityAnalysisResult
} from "./ToxicityAnalysisTypes.js";

export class ToxicityBackendClientError extends Error {
  public constructor(
    message: string,
    public readonly statusCode?: number,
    public readonly isTemporary = false,
    public readonly details?: ProblemDetailsError
  ) {
    super(message);
  }
}

export class ToxicityBackendTimeoutError extends ToxicityBackendClientError {
  public constructor(timeoutMs: number) {
    super(`Backend request timed out after ${timeoutMs}ms.`, 504, true);
  }
}

export interface ToxicityBackendClientOptions {
  baseUrl: string;
  timeoutMs: number;
  authToken?: string;
  serviceClientId?: string;
  serviceClientSecret?: string;
  fetchImpl?: typeof fetch;
}

export class ToxicityBackendClient {
  private readonly fetchImpl: typeof fetch;
  private readonly endpoint: URL;
  private readonly serviceTokenEndpoint: URL;
  private cachedAccessToken?: CachedAccessToken;

  public constructor(private readonly options: ToxicityBackendClientOptions) {
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.endpoint = new URL("/api/v1/toxicity/analyze", ensureTrailingSlash(options.baseUrl));
    this.serviceTokenEndpoint = new URL("/api/v1/auth/service-token", ensureTrailingSlash(options.baseUrl));
  }

  public async analyze(text: string): Promise<ToxicityAnalysisResult> {
    const abortController = new AbortController();
    const timeout = setTimeout(() => abortController.abort(), this.options.timeoutMs);

    try {
      const response = await this.fetchImpl(this.endpoint, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          ...createAuthorizationHeader(await this.getAuthorizationToken())
        },
        body: JSON.stringify({
          text,
          reportLevel: "full"
        }),
        signal: abortController.signal
      });

      const payload = await parseJsonResponse(response);

      if (!response.ok) {
        throw new ToxicityBackendClientError(
          `Backend analyze request failed with status ${response.status}.`,
          response.status,
          isTemporaryStatus(response.status),
          isProblemDetailsError(payload) ? payload : undefined
        );
      }

      return toxicityAnalysisResultSchema.parse(payload);
    } catch (error: unknown) {
      if (isAbortError(error)) {
        throw new ToxicityBackendTimeoutError(this.options.timeoutMs);
      }

      if (error instanceof ToxicityBackendClientError) {
        throw error;
      }

      throw new ToxicityBackendClientError("Backend analyze request failed.", undefined, true);
    } finally {
      clearTimeout(timeout);
    }
  }

  private async getAuthorizationToken(): Promise<string | undefined> {
    if (this.options.authToken !== undefined) {
      return this.options.authToken;
    }

    if (this.options.serviceClientId === undefined || this.options.serviceClientSecret === undefined) {
      return undefined;
    }

    if (this.cachedAccessToken !== undefined && this.cachedAccessToken.expiresAt > Date.now() + 30_000) {
      return this.cachedAccessToken.accessToken;
    }

    const response = await this.fetchImpl(this.serviceTokenEndpoint, {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        clientId: this.options.serviceClientId,
        clientSecret: this.options.serviceClientSecret
      })
    });

    const payload = await parseJsonResponse(response);

    if (!response.ok || !isServiceTokenResponse(payload)) {
      throw new ToxicityBackendClientError(
        `Backend service-token request failed with status ${response.status}.`,
        response.status,
        isTemporaryStatus(response.status),
        isProblemDetailsError(payload) ? payload : undefined
      );
    }

    this.cachedAccessToken = {
      accessToken: payload.accessToken,
      expiresAt: Date.parse(payload.expiresAt)
    };

    return this.cachedAccessToken.accessToken;
  }
}

function ensureTrailingSlash(baseUrl: string): string {
  return baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`;
}

async function parseJsonResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";

  if (!contentType.includes("application/json")) {
    return null;
  }

  return response.json();
}

function isTemporaryStatus(statusCode: number): boolean {
  return statusCode === 503 || statusCode === 504 || statusCode >= 500;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function isProblemDetailsError(value: unknown): value is ProblemDetailsError {
  return typeof value === "object" && value !== null;
}

function createAuthorizationHeader(authToken?: string): Record<string, string> {
  return authToken
    ? { authorization: `Bearer ${authToken}` }
    : {};
}

function isServiceTokenResponse(value: unknown): value is ServiceTokenResponse {
  return typeof value === "object" &&
    value !== null &&
    typeof (value as ServiceTokenResponse).accessToken === "string" &&
    typeof (value as ServiceTokenResponse).expiresAt === "string";
}

interface CachedAccessToken {
  accessToken: string;
  expiresAt: number;
}

interface ServiceTokenResponse {
  accessToken: string;
  expiresAt: string;
}
