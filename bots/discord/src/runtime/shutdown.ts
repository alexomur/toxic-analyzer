import type { Logger } from "pino";

export function registerGracefulShutdown(
  shutdown: () => Promise<void>,
  logger: Logger
): void {
  const signals: NodeJS.Signals[] = ["SIGINT", "SIGTERM"];
  let shuttingDown = false;

  const handler = (signal: NodeJS.Signals) => {
    if (shuttingDown) {
      return;
    }

    shuttingDown = true;

    logger.info({ signal }, "Received shutdown signal.");

    void shutdown()
      .catch((error: unknown) => {
        logger.error({ error }, "Graceful shutdown failed.");
        process.exitCode = 1;
      })
      .finally(() => {
        process.exit();
      });
  };

  for (const signal of signals) {
    process.once(signal, handler);
  }
}
