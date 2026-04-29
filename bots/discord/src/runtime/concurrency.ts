export function createConcurrencyLimiter(limit: number) {
  let activeCount = 0;
  const queue: Array<() => void> = [];

  return async function runWithLimit<T>(operation: () => Promise<T>): Promise<T> {
    if (activeCount >= limit) {
      await new Promise<void>((resolve) => {
        queue.push(resolve);
      });
    }

    activeCount += 1;

    try {
      return await operation();
    } finally {
      activeCount -= 1;
      queue.shift()?.();
    }
  };
}
