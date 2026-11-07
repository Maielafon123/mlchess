export type ConnectionState = "online" | "offline" | "resyncing" | "out-of-sync";

export function backoffDelay(attempt: number, baseMs = 250, maxMs = 4000) {
  return Math.min(maxMs, baseMs * 2 ** Math.max(0, attempt));
}

export async function withRetry<T>(operation: () => Promise<T>, options: { retries?: number; delay?: (attempt: number) => number; sleep?: (ms: number) => Promise<void> } = {}) {
  const retries = options.retries ?? 2;
  const delay = options.delay ?? backoffDelay;
  const sleep = options.sleep ?? ((ms: number) => new Promise<void>((resolve) => window.setTimeout(resolve, ms)));
  let attempt = 0;
  while (true) {
    try { return await operation(); } catch (error) {
      if (attempt >= retries) throw error;
      await sleep(delay(attempt));
      attempt += 1;
    }
  }
}

export class SafeMoveRetry<T> {
  private readonly commands = new Map<string, () => Promise<T>>();
  register(clientMoveId: string, operation: () => Promise<T>) { this.commands.set(clientMoveId, operation); return clientMoveId; }
  retry(clientMoveId: string) { const operation = this.commands.get(clientMoveId); return operation ? withRetry(operation) : Promise.reject(new Error("Move command not found")); }
  clear(clientMoveId: string) { this.commands.delete(clientMoveId); }
}
