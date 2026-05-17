/**
 * Provider Health Tracker - Динамический scoring провайдеров
 */

export type ProviderHealthState = 'UP' | 'DEGRADED' | 'DOWN';

export interface ProviderHealthSnapshot {
  providerId: string;
  score: number;
  state: ProviderHealthState;
  lastMessageAt: number | null;
  lastErrorAt: number | null;
  consecutiveFailures: number;
}

export class ProviderHealthTracker {
  private state = new Map<string, ProviderHealthSnapshot>();

  init(providerId: string) {
    if (this.state.has(providerId)) return;

    this.state.set(providerId, {
      providerId,
      score: 100,
      state: 'UP',
      lastMessageAt: null,
      lastErrorAt: null,
      consecutiveFailures: 0,
    });
  }

  markMessage(providerId: string) {
    this.init(providerId);
    const item = this.state.get(providerId)!;

    item.lastMessageAt = Date.now();
    item.consecutiveFailures = 0;
    item.score = Math.min(100, item.score + 2);
    item.state = this.scoreToState(item.score);
  }

  markError(providerId: string) {
    this.init(providerId);
    const item = this.state.get(providerId)!;

    item.lastErrorAt = Date.now();
    item.consecutiveFailures += 1;
    item.score = Math.max(0, item.score - 15);
    item.state = this.scoreToState(item.score);
  }

  markStale(providerId: string) {
    this.init(providerId);
    const item = this.state.get(providerId)!;

    item.score = Math.max(0, item.score - 10);
    item.state = this.scoreToState(item.score);
  }

  get(providerId: string): ProviderHealthSnapshot {
    this.init(providerId);
    return { ...this.state.get(providerId)! };
  }

  getAll(): ProviderHealthSnapshot[] {
    return [...this.state.values()].map((v) => ({ ...v }));
  }

  private scoreToState(score: number): ProviderHealthState {
    if (score >= 70) return 'UP';
    if (score >= 35) return 'DEGRADED';
    return 'DOWN';
  }
}

// Singleton instance
export const providerHealthTracker = new ProviderHealthTracker();
