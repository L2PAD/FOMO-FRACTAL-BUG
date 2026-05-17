/**
 * Push Engine — Shared Types
 * ===========================
 * Decision layer: detect market state changes and emit push candidates.
 *
 * Detector gradation:
 *   FORMING     — alpha > 0.45 && velocity > 1   → first emission
 *   CONFIRMED   — alpha > 0.65 && aligned strong  → stage escalation
 *   TENSION     — mixed directions across top 5   → market-level event
 *   PERSONAL    — asset ∈ user.recentAssets      → user-scoped reminder
 *
 * No event fires twice for the same (eventId, pushType) — see push_state.
 */

export type PushType =
  | 'FORMING'
  | 'CONFIRMED'
  | 'MISSED'
  | 'TENSION'
  | 'PERSONAL'
  // ── Product signal types (sentiment-driven) ──
  | 'LISTING'     // new CEX/DEX listing — CRITICAL
  | 'EXPLOIT'     // protocol exploit detected — CRITICAL
  | 'ETF'         // ETF-related development — CRITICAL
  | 'REGULATION'  // regulation / legal news — HIGH
  // ── Product signal types (polymarket-driven, market-first) ──
  | 'POLY_MISPRICING'       // new_mispricing — CRITICAL
  | 'POLY_REPRICING'        // repricing_started/change — HIGH/MEDIUM
  | 'POLY_OVERHEATED'       // overheated — HIGH
  | 'POLY_THESIS_WEAKENED'  // thesis_weakened / entry_window_closed — HIGH/MEDIUM
  // ── News (breaking / market-moving) ──
  | 'NEWS';                 // classifier-gated; market-first; CRITICAL|HIGH|MEDIUM
export type PushStage = 'EARLY' | 'FORMING' | 'CONFIRMED' | 'SATURATED';
export type UnifiedCategory = 'retention' | 'alert' | 'system';
export type UnifiedSource = 'push_engine' | 'python' | 'fomo' | 'external';
export type SubscriberRole = 'user' | 'admin';

/**
 * UnifiedEvent — single shape every source normalizes to before routing.
 * Push Router is the ONLY consumer of this shape.
 */
export interface UnifiedEvent {
  id: string;                           // stable dedupe key across retries
  category: UnifiedCategory;
  source: UnifiedSource;
  type: PushType | string;              // subtype within category
  asset?: string | null;
  stage?: PushStage;
  alpha?: number;
  severity?: 'low' | 'medium' | 'high' | 'critical';
  reason?: string;
  deepLink?: string;
  timestamp: number;                    // epoch ms
  forUserId?: string;                   // Targeted delivery — only this user receives it (used by MISSED/PERSONAL retention loop)
  meta?: Record<string, any>;
}

export interface DetectedEvent {
  type: PushType;
  eventId: string;           // stable id (clusterId for cluster-bound, 'tension:<bucket>' for market)
  clusterId?: string;
  asset: string | null;
  stage: PushStage;
  alpha: number;             // 0..1
  reason: string;            // human-readable reason for admin
  title: string;             // Bloomberg-tone push title
  body: string;              // short body (< 60 chars)
  deepLink: string;          // fomo://news?asset=TRX
  priority: 'high' | 'normal';
  createdAt: Date;
  meta: Record<string, any>; // context snapshot (sourcesCount, velocity, ...)
}

export interface PushQueueItem {
  _id?: any;
  userId: string | null;     // null = broadcast / TENSION
  eventId: string;
  type: PushType;
  asset: string | null;
  stage: PushStage;
  alpha: number;
  reason: string;
  title: string;
  body: string;
  deepLink: string;
  status: 'pending' | 'sent' | 'skipped';
  skipReason?: string;
  createdAt: Date;
  sentAt?: Date;
  channel?: 'mock' | 'telegram' | 'expo';
}

export interface PushLog {
  userId: string | null;
  eventId: string;
  type: PushType;
  asset: string | null;
  title: string;
  body: string;
  channel: 'mock' | 'telegram' | 'expo';
  ts: Date;
}

export interface PushStateDoc {
  eventId: string;             // = clusterId for cluster events
  lastStage: PushStage | null;
  lastAlpha: number;
  pushedAt: Date | null;
  pushTypesSent: PushType[];   // dedupe guard
  updatedAt: Date;
}

export interface PushSubscriber {
  userId: string;
  role?: SubscriberRole;               // 'user' (default) | 'admin' — routes message style
  telegramChatId?: string | null;
  expoToken?: string | null;
  recentAssets: string[];              // persisted server-side mirror of client's AsyncStorage
  lastPushAt?: Date | null;
  lastPushedAsset?: string | null;
  pushCount24h: number;
  pushCount24hResetAt: Date;
  muted?: boolean;
  createdAt: Date;
}

export interface DetectorCycleReport {
  ts: Date;
  scanned: number;             // clusters scanned
  emitted: number;             // events emitted this cycle
  byType: Record<PushType, number>;
  skippedDup: number;
  skippedThreshold: number;
  tookMs: number;
}
