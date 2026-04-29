export async function withRetry<T>(
  operation: () => Promise<T>,
  retries: number,
  delayMs: number,
  shouldRetry: (error: unknown) => boolean
): Promise<T> {
  let attempt = 0;

  while (true) {
    try {
      return await operation();
    } catch (error: unknown) {
      attempt += 1;

      if (attempt > retries || !shouldRetry(error)) {
        throw error;
      }

      await sleep(delayMs * attempt);
    }
  }
}

function sleep(delayMs: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, delayMs);
  });
}
