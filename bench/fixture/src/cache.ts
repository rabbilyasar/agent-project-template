export interface CacheEntry<T> {
  value: T;
  expiresAt: number;
}

export class TtlCache<T> {
  private store = new Map<string, CacheEntry<T>>();

  constructor(private now: () => number = Date.now) {}

  set(key: string, value: T, ttlMs: number): void {
    this.store.set(key, { value, expiresAt: this.now() + ttlMs });
  }

  has(key: string): boolean {
    const entry = this.store.get(key);
    if (!entry) return false;
    return this.now() < entry.expiresAt;
  }

  // Seeded bug for bench/tasks/investigation-debugging.md: this does not
  // check expiresAt, so a caller can read a stale value after the key has
  // expired even though has() correctly reports it as gone. The fix belongs
  // here, not in each caller of get().
  get(key: string): T | undefined {
    return this.store.get(key)?.value;
  }
}
