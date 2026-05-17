/**
 * Sentiment Parser Health Guard Service
 * =======================================
 * 
 * BLOCK 10.2: Monitors parser health and data availability.
 * 
 * Checks:
 * - Cookie/session status
 * - Data freshness (time since last tweet)
 * - Ingestion rate (events per hour)
 * - Error rate
 * 
 * Actions:
 * - CRITICAL: Kill switch ON, all workers stop
 * - DEGRADED: Training disabled
 * - WARN: Inference confidence lowered
 */

import { SentimentGuardStateModel, GuardStatus, GuardReason } from './sentiment_guard_state.model.js';
import mongoose from 'mongoose';

export type HealthMetrics = {
  now: Date;
  lastEventAt: Date | null;
  events6h: number;
  events24h: number;
  errors6h: number;
  parserErrors6h: number;
  cookiesAvailable: boolean;
  activeSessions: number;
};

export type GuardDecision = {
  status: GuardStatus;
  reasons: GuardReason[];
  isKillSwitchOn: boolean;
  isTrainingDisabled: boolean;
  isInferenceDegraded: boolean;
  metrics: HealthMetrics;
};

// Thresholds (production-safe)
const THRESHOLDS = {
  staleCriticalHours: 6,
  staleDegradedHours: 2,
  minEvents6h: 5,
  minEvents24h: 30,
  errorsCritical: 20,
  errorsDegraded: 8,
};

export class SentimentParserHealthGuardService {
  /**
   * Run health check and update guard state
   */
  async runCheck(now: Date = new Date()): Promise<GuardDecision> {
    const metrics = await this.collectMetrics(now);
    const decision = await this.decide(metrics);

    // Save to MongoDB
    await SentimentGuardStateModel.updateOne(
      { key: 'sentiment_parser_health' },
      {
        $set: {
          status: decision.status,
          reasons: decision.reasons,
          isKillSwitchOn: decision.isKillSwitchOn,
          isTrainingDisabled: decision.isTrainingDisabled,
          isInferenceDegraded: decision.isInferenceDegraded,
          details: { 
            metrics: decision.metrics, 
            decisionAt: now,
            thresholds: THRESHOLDS,
          },
        },
      },
      { upsert: true }
    );

    console.log(`[ParserGuard] Status: ${decision.status}, Reasons: ${decision.reasons.join(', ') || 'none'}`);
    
    return decision;
  }

  /**
   * Collect health metrics from database
   */
  private async collectMetrics(now: Date): Promise<HealthMetrics> {
    const db = mongoose.connection.db;
    if (!db) {
      return {
        now,
        lastEventAt: null,
        events6h: 0,
        events24h: 0,
        errors6h: 0,
        parserErrors6h: 0,
        cookiesAvailable: false,
        activeSessions: 0,
      };
    }

    const since6h = new Date(now.getTime() - 6 * 3600_000);
    const since24h = new Date(now.getTime() - 24 * 3600_000);

    // Check sentiment_events for recent activity
    let lastEventAt: Date | null = null;
    let events6h = 0;
    let events24h = 0;

    try {
      const eventsColl = db.collection('sentiment_events');
      
      // Last event
      const lastEvent = await eventsColl.findOne(
        {},
        { sort: { createdAt: -1 }, projection: { createdAt: 1 } }
      );
      lastEventAt = lastEvent?.createdAt || null;

      // Count events
      events6h = await eventsColl.countDocuments({
        createdAt: { $gte: since6h, $lte: now },
      });
      events24h = await eventsColl.countDocuments({
        createdAt: { $gte: since24h, $lte: now },
      });
    } catch (err) {
      console.error('[ParserGuard] Error checking events:', err);
    }

    // Check ops errors
    let errors6h = 0;
    let parserErrors6h = 0;

    try {
      const errorsColl = db.collection('sentiment_ops_errors');
      errors6h = await errorsColl.countDocuments({
        ts: { $gte: since6h, $lte: now },
      });
      parserErrors6h = await errorsColl.countDocuments({
        ts: { $gte: since6h, $lte: now },
        source: { $in: ['parser', 'twitter', 'intake'] },
      });
    } catch {
      // Errors collection might not exist
    }

    // Check cookie sessions (if available)
    // FIX: Guard was querying { isValid, expiresAt } but actual schema uses { isActive, status }
    let cookiesAvailable = true;
    let activeSessions = 0;

    try {
      const sessionsColl = db.collection('twitter_sessions');
      // Match actual session model: isActive + status='OK'
      activeSessions = await sessionsColl.countDocuments({
        $or: [
          { isActive: true, status: 'OK' },
          { status: 'OK' },
        ],
      });
      // Fallback: count any non-expired, non-error sessions
      if (activeSessions === 0) {
        activeSessions = await sessionsColl.countDocuments({
          status: { $in: ['OK', 'STALE'] },
        });
      }
      cookiesAvailable = activeSessions > 0;
    } catch {
      // Sessions collection might not exist, assume OK if events exist
      cookiesAvailable = events24h > 0;
      activeSessions = events24h > 0 ? 1 : 0;
    }

    return {
      now,
      lastEventAt,
      events6h,
      events24h,
      errors6h,
      parserErrors6h,
      cookiesAvailable,
      activeSessions,
    };
  }

  /**
   * Make guard decision based on metrics
   */
  private async decide(m: HealthMetrics): Promise<GuardDecision> {
    const reasons: GuardReason[] = [];
    
    // Calculate hours since last event
    const hoursSinceLastEvent = m.lastEventAt
      ? (m.now.getTime() - new Date(m.lastEventAt).getTime()) / 3600_000
      : 1e9;

    // Check conditions
    if (!m.cookiesAvailable && m.activeSessions === 0) {
      reasons.push('COOKIES_MISSING');
    }
    
    if (hoursSinceLastEvent >= THRESHOLDS.staleCriticalHours) {
      reasons.push('STALE_DATA');
    }
    
    if (m.events6h === 0 && hoursSinceLastEvent >= 2) {
      reasons.push('ZERO_INGEST');
    }
    
    if (m.events24h < THRESHOLDS.minEvents24h) {
      reasons.push('LOW_VOLUME');
    }
    
    if (m.parserErrors6h >= THRESHOLDS.errorsCritical) {
      reasons.push('HIGH_ERROR_RATE');
    }

    // Determine status
    let status: GuardStatus = 'OK';

    const isCritical = 
      reasons.includes('COOKIES_MISSING') ||
      reasons.includes('STALE_DATA') ||
      reasons.includes('ZERO_INGEST') ||
      m.parserErrors6h >= THRESHOLDS.errorsCritical;

    const isDegraded =
      hoursSinceLastEvent >= THRESHOLDS.staleDegradedHours ||
      m.parserErrors6h >= THRESHOLDS.errorsDegraded ||
      m.events6h < THRESHOLDS.minEvents6h;

    const isWarn =
      m.events24h < THRESHOLDS.minEvents24h * 2 ||
      m.parserErrors6h >= 3;

    if (isCritical) {
      status = 'CRITICAL';
    } else if (isDegraded) {
      status = 'DEGRADED';
    } else if (isWarn) {
      status = 'WARN';
    }

    // Determine actions
    // If kill switch was manually disabled (recovery mode), respect the override
    const currentState = await SentimentGuardStateModel.findOne({ key: 'sentiment_parser_health' }).lean() as any;
    const hasManualOverride = currentState?.details?.manual === true && currentState?.isKillSwitchOn === false;

    const isKillSwitchOn = hasManualOverride ? false : status === 'CRITICAL';
    const isTrainingDisabled = hasManualOverride ? false : (status === 'CRITICAL' || status === 'DEGRADED');
    const isInferenceDegraded = status !== 'OK';

    return {
      status,
      reasons,
      isKillSwitchOn,
      isTrainingDisabled,
      isInferenceDegraded,
      metrics: m,
    };
  }

  /**
   * Get current guard state
   */
  async getState(): Promise<any> {
    return SentimentGuardStateModel.findOne({ key: 'sentiment_parser_health' }).lean();
  }

  /**
   * Manual kill switch control
   */
  async setKillSwitch(enabled: boolean, note?: string): Promise<void> {
    await SentimentGuardStateModel.updateOne(
      { key: 'sentiment_parser_health' },
      {
        $set: {
          status: enabled ? 'CRITICAL' : 'OK',
          reasons: enabled ? ['MANUAL_KILL'] : [],
          isKillSwitchOn: enabled,
          isTrainingDisabled: enabled,
          isInferenceDegraded: enabled,
          details: { manual: true, note: note || null, at: new Date() },
        },
      },
      { upsert: true }
    );
  }

  /**
   * Check if workers are allowed to run
   */
  async isWorkersAllowed(): Promise<boolean> {
    const state = await this.getState();
    return !state?.isKillSwitchOn;
  }

  /**
   * Check if training is allowed
   */
  async isTrainingAllowed(): Promise<boolean> {
    const state = await this.getState();
    return !state?.isTrainingDisabled;
  }

  /**
   * Get confidence modifier based on guard state
   */
  async getConfidenceModifier(): Promise<number> {
    const state = await this.getState();
    if (!state) return 1.0;
    
    switch (state.status) {
      case 'CRITICAL': return 0.5;
      case 'DEGRADED': return 0.7;
      case 'WARN': return 0.9;
      default: return 1.0;
    }
  }
}

// Singleton
let guardServiceInstance: SentimentParserHealthGuardService | null = null;

export function getSentimentParserHealthGuard(): SentimentParserHealthGuardService {
  if (!guardServiceInstance) {
    guardServiceInstance = new SentimentParserHealthGuardService();
  }
  return guardServiceInstance;
}

console.log('[Sentiment-ML] Parser Health Guard Service loaded (BLOCK 10.2)');
