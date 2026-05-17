/**
 * Twitter Standby Monitor
 * =======================
 * Monitors Twitter session health and manages standby/active state transitions.
 * 
 * When all sessions are invalid/expired → enters STANDBY mode
 * When valid sessions appear → transitions to ACTIVE mode
 * 
 * Logs state transitions clearly, no error-spamming.
 */

import { TwitterSessionModel } from '../modules/twitter/sessions/session.model.js';

export type StandbyState = 'ACTIVE' | 'STANDBY' | 'UNKNOWN';

export interface StandbyStatus {
  state: StandbyState;
  stateChangedAt: Date | null;
  totalSessions: number;
  okSessions: number;
  staleSessions: number;
  expiredSessions: number;
  lastCheckAt: Date | null;
  checkCount: number;
  standbyDurationMs: number;
}

class TwitterStandbyMonitor {
  private state: StandbyState = 'UNKNOWN';
  private stateChangedAt: Date | null = null;
  private lastCheckAt: Date | null = null;
  private checkCount = 0;
  private timer: NodeJS.Timeout | null = null;
  private lastLogAt = 0;
  
  // Last check session stats
  private lastTotal = 0;
  private lastOk = 0;
  private lastStale = 0;
  private lastExpired = 0;

  // Log standby reminder every 10 minutes (not every check)
  private readonly STANDBY_LOG_INTERVAL_MS = 10 * 60 * 1000;
  // Check interval: 2 minutes
  private readonly CHECK_INTERVAL_MS = 2 * 60 * 1000;

  /**
   * Start periodic session health monitoring
   */
  start(): void {
    if (this.timer) return;

    console.log('[TwitterStandby] Monitor started (check every 2min)');

    // Initial check after 15 seconds
    setTimeout(() => this.check(), 15_000);

    this.timer = setInterval(() => this.check(), this.CHECK_INTERVAL_MS);
  }

  /**
   * Stop the monitor
   */
  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    console.log('[TwitterStandby] Monitor stopped');
  }

  /**
   * Get current standby status
   */
  getStatus(): StandbyStatus {
    const standbyDurationMs = this.state === 'STANDBY' && this.stateChangedAt
      ? Date.now() - this.stateChangedAt.getTime()
      : 0;

    return {
      state: this.state,
      stateChangedAt: this.stateChangedAt,
      totalSessions: this.lastTotal,
      okSessions: this.lastOk,
      staleSessions: this.lastStale,
      expiredSessions: this.lastExpired,
      lastCheckAt: this.lastCheckAt,
      checkCount: this.checkCount,
      standbyDurationMs,
    };
  }

  /**
   * Perform a health check on all Twitter sessions
   */
  private async check(): Promise<void> {
    this.checkCount++;
    this.lastCheckAt = new Date();

    try {
      const sessions = await TwitterSessionModel.find({}).lean();
      const total = sessions.length;
      const ok = sessions.filter(s => s.status === 'OK').length;
      const stale = sessions.filter(s => s.status === 'STALE').length;
      const expired = sessions.filter(s => s.status === 'EXPIRED' || s.status === 'INVALID').length;
      const error = sessions.filter(s => s.status === 'ERROR').length;

      // Store stats for getStatus()
      this.lastTotal = total;
      this.lastOk = ok;
      this.lastStale = stale;
      this.lastExpired = expired;

      const hasValidSessions = ok > 0;
      const previousState = this.state;

      if (total === 0) {
        // No sessions at all — standby
        this.transitionTo('STANDBY', 'No Twitter sessions configured');
      } else if (!hasValidSessions) {
        // All sessions invalid/expired/stale — standby
        this.transitionTo('STANDBY', `All ${total} sessions unavailable (stale=${stale}, expired=${expired}, error=${error})`);
      } else {
        // At least one valid session — active
        this.transitionTo('ACTIVE', `${ok}/${total} sessions OK`);
      }

      // Periodic standby reminder (every 10 min, not every check)
      if (this.state === 'STANDBY' && Date.now() - this.lastLogAt > this.STANDBY_LOG_INTERVAL_MS) {
        const durationMin = this.stateChangedAt
          ? Math.round((Date.now() - this.stateChangedAt.getTime()) / 60000)
          : 0;
        console.log(`[TwitterStandby] Still in STANDBY (${durationMin}min). Waiting for valid cookies... (total=${total}, ok=${ok}, stale=${stale}, expired=${expired})`);
        this.lastLogAt = Date.now();
      }
    } catch (err: any) {
      // Don't crash on DB errors — just log and continue
      console.warn(`[TwitterStandby] Check failed: ${err.message}`);
    }
  }

  /**
   * Handle state transition with logging
   */
  private transitionTo(newState: StandbyState, reason: string): void {
    if (this.state === newState) return;

    const previousState = this.state;
    this.state = newState;
    this.stateChangedAt = new Date();
    this.lastLogAt = Date.now();

    if (newState === 'STANDBY') {
      console.log(`[TwitterStandby] ⏸ ENTERING STANDBY (was ${previousState}): ${reason}`);
      console.log(`[TwitterStandby] Parser will auto-resume when valid cookies are detected`);
    } else if (newState === 'ACTIVE') {
      console.log(`[TwitterStandby] ▶ RESUMING ACTIVE (was ${previousState}): ${reason}`);
      console.log(`[TwitterStandby] Parser sessions available, processing can proceed`);
    }
  }

  /**
   * Check if parser is in standby (for external consumers)
   */
  isInStandby(): boolean {
    return this.state === 'STANDBY';
  }
}

export const twitterStandbyMonitor = new TwitterStandbyMonitor();
