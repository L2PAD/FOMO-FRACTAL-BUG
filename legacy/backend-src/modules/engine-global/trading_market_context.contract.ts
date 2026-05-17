/**
 * TradingMarketContext — Brain-Bridge contract (Phase 0)
 * =======================================================
 *
 * Defines the normalized market context that flows from the
 * **Analytical Brain** through the **brain_bridge** to the
 * **Trading Meta-Brain**.
 *
 * This file is a **CONTRACT ONLY** — there is no implementation in
 * Phase 0. The bridge service that produces these objects will be
 * built in a separate task. Until then, consumers MUST handle `null`
 * fields gracefully (honest-degraded mode).
 *
 * --------------------------------------------------------------------
 * Key principles (DO NOT VIOLATE):
 *
 *   1. **No fake confidence**. If a sensor cannot provide data, the
 *      whole sensor block is `null`, OR fields inside it are explicit
 *      `'unknown'` / `0`. We never ship `confidence: 0.75` when we
 *      have no evidence.
 *
 *   2. **`source` is mandatory**. Every populated context block must
 *      declare where the data came from. This makes upstream changes
 *      auditable and prevents silent source swaps.
 *
 *   3. **`asOf` is mandatory**. Every populated context block must
 *      declare its timestamp. Stale data is acceptable only if it is
 *      *visible*. The trading layer can decide to ignore or discount
 *      stale signals.
 *
 *   4. **`bridgeHealth` reports honestly**. `*_ok: true` means the
 *      bridge actually got non-empty data, not just an HTTP 200.
 *
 *   5. **No business logic in the contract**. No thresholds, no
 *      derived directions, no trading actions. Just observed state.
 * --------------------------------------------------------------------
 *
 * Origin: docs/audit/MBRAIN_ARCHITECTURE_AUDIT.md (Variant B chosen).
 * Source survey: docs/audit/SENTIMENT_ONCHAIN_SOURCES_AUDIT.md.
 */

// ═════════════════════════════════════════════════════════════════════
// Per-sensor context blocks
// ═════════════════════════════════════════════════════════════════════

/**
 * Fractal market state — produced by the Analytical Brain via
 * `/modules/brain/contracts/asset_state.contract.ts` (FractalPack).
 *
 * The bridge collapses the brain's 4-layer FractalPack
 * (replay/synthetic/hybrid/macro) into a single readable summary
 * for the trading layer. Layer-level detail stays in analytics.
 */
export interface FractalContext {
  /** Coarse fractal state. `'unknown'` means no signal available. */
  state: 'breakdown' | 'breakout' | 'rangebound' | 'unknown';
  /** Confidence [0..1]. 0 = no evidence. */
  confidence: number;
  /** Risk read attached to the fractal layer. */
  risk: 'low' | 'medium' | 'high' | 'unknown';
  /**
   * Where the underlying data came from. Useful for audit and for
   * future source migrations.
   *   - 'analytical_brain' : produced by the analytical brain pack
   *   - 'degraded'         : analytical brain returned but with
   *                          incomplete data (we kept what we have)
   *   - 'unavailable'      : block should be `null`, not this string;
   *                          this value exists only as a defensive
   *                          fallback if a future producer cannot use
   *                          a `null` envelope
   */
  source: 'analytical_brain' | 'degraded' | 'unavailable';
  /** ISO timestamp of the data point. */
  asOf: string;
}

/**
 * Sentiment state. Phase 0 canonical source = `intelligence-v1`
 * aggregate (see SENTIMENT_ONCHAIN_SOURCES_AUDIT.md). Future migration
 * may flip this to 'sentiment-ml' or 'social-intelligence' once those
 * provide a single canonical aggregate endpoint.
 */
export interface SentimentContext {
  state: 'bullish' | 'bearish' | 'neutral' | 'unknown';
  /** Sentiment score in [-1..1]. 0 = neutral / no signal. */
  score: number;
  confidence: number;
  source:
    | 'intelligence-v1'
    | 'sentiment-ml'
    | 'social-intelligence'
    | 'degraded'
    | 'unavailable';
  asOf: string;
}

/**
 * Onchain state. Phase 0 canonical source = `intelligence-v1`
 * aggregate. Phase 2 target = `/modules/onchain_v2/`. Until v2 is
 * mounted on the side-car, this block will frequently be `null` or
 * `degraded` — that is the *correct* behaviour.
 */
export interface OnchainContext {
  state: 'accumulation' | 'distribution' | 'neutral' | 'unknown';
  /** Composite onchain score in [-1..1]. 0 = neutral / no signal. */
  score: number;
  confidence: number;
  source:
    | 'intelligence-v1'
    | 'onchain'
    | 'onchain_v2'
    | 'degraded'
    | 'unavailable';
  asOf: string;
}

// ═════════════════════════════════════════════════════════════════════
// Bridge health
// ═════════════════════════════════════════════════════════════════════

/**
 * Per-sensor health flags. `true` ONLY when the bridge got a non-empty
 * payload AND was able to populate a context block (not null).
 *
 * Reason strings are short, machine-readable, and primarily for
 * logs / UI explainers ("3/3 sensors live · 0 degraded").
 *
 * Per-sensor latency is captured in milliseconds. A sensor that timed
 * out reports `_ms` equal to or greater than the timeout budget (see
 * `BRIDGE_TIMEOUT_BUDGET_MS` below) AND `*_ok: false`. Latencies enable
 * downstream telemetry to:
 *   - rank provider reliability,
 *   - correlate slow upstreams with degraded verdicts,
 *   - detect bridge regressions.
 */
export interface TradingBridgeHealth {
  fractal_ok: boolean;
  sentiment_ok: boolean;
  onchain_ok: boolean;
  /** Per-sensor wall-clock latency in milliseconds (0 if not attempted). */
  fractal_ms: number;
  sentiment_ms: number;
  onchain_ms: number;
  /** Free-form reason map for any sensor that is NOT ok. */
  reasons: Partial<{
    fractal: string;
    sentiment: string;
    onchain: string;
  }>;
}

/**
 * Hard upper bound on total bridge wall-clock time, in milliseconds.
 *
 * The bridge service MUST NOT block the verdict pipeline beyond this
 * budget. Per-sensor calls run concurrently; any sensor exceeding the
 * budget is reported as `*_ok: false` with reason `'timeout'` and the
 * verdict pipeline proceeds with whatever sensors completed.
 *
 * Verdicts are produced even when ALL sensors time out — the trading
 * meta-brain falls back to its native sources (TA + Exchange).
 *
 * This constant is part of the contract because the timeout discipline
 * is a non-negotiable property of the bridge, not an implementation
 * choice. Changing this value requires updating the contract version.
 */
export const BRIDGE_TIMEOUT_BUDGET_MS = 600 as const;

/**
 * Aggregated, derived health snapshot — convenience view computed from
 * `TradingBridgeHealth`. Used by:
 *   - UI layer ("3/3 sensors live", "Sentiment degraded", "Onchain unavailable")
 *   - analytics / observability ("bridge uptime", "sensor reliability",
 *     "verdict coverage quality")
 *
 * NOT a separate data path — this MUST be derived from the same
 * `bridgeHealth` block on the parent context. The bridge service
 * computes it once and exposes it for read-only consumption.
 */
export interface BridgeHealthSnapshot {
  /** Percentage of sensors that returned `*_ok: true`. 0..100, integer. */
  coveragePct: number;
  /** Sensors whose block on the context is `null` or `*_ok: false`. */
  missing: Array<'fractal' | 'sentiment' | 'onchain'>;
  /** True if at least one sensor is `*_ok: false`. */
  degraded: boolean;
}

/**
 * Pure helper — derive a `BridgeHealthSnapshot` from
 * `TradingBridgeHealth`. Stateless, deterministic, side-effect-free.
 * Lives in the contract file so producers and consumers compute health
 * the same way.
 */
export function deriveBridgeHealthSnapshot(
  h: TradingBridgeHealth,
): BridgeHealthSnapshot {
  const flags: Array<['fractal' | 'sentiment' | 'onchain', boolean]> = [
    ['fractal', h.fractal_ok],
    ['sentiment', h.sentiment_ok],
    ['onchain', h.onchain_ok],
  ];
  const okCount = flags.filter(([, ok]) => ok).length;
  const missing = flags.filter(([, ok]) => !ok).map(([k]) => k);
  return {
    coveragePct: Math.round((okCount / flags.length) * 100),
    missing,
    degraded: missing.length > 0,
  };
}

// ═════════════════════════════════════════════════════════════════════
// Top-level context envelope
// ═════════════════════════════════════════════════════════════════════

/**
 * Single value passed by `brain_bridge.service.ts` to the Trading
 * Meta-Brain on each verdict evaluation.
 *
 * Must be **constructible without any sensor data** (everything
 * `null`, all health flags `false`). The trading layer must produce
 * a verdict in that case using only its native sources (TA + Exchange).
 *
 * Fields are intentionally non-optional in TypeScript so consumers
 * cannot "forget" to handle a sensor — they must explicitly check
 * for `null`.
 */
export interface TradingMarketContext {
  /** Symbol the context refers to (e.g. 'BTCUSDT'). */
  symbol: string;
  /** Bridge build timestamp (ISO). */
  ts: string;

  /** External sensors fed via brain_bridge. `null` = sensor unavailable. */
  fractal: FractalContext | null;
  sentiment: SentimentContext | null;
  onchain: OnchainContext | null;

  /** Health flags so the trading layer knows what is missing. */
  bridgeHealth: TradingBridgeHealth;

  /**
   * Bridge-implementation version. Lets the trading layer be
   * defensive about contract drift.
   */
  contractVersion: 'v0';
}

// ═════════════════════════════════════════════════════════════════════
// Helper — empty (honest-degraded) constructor
// ═════════════════════════════════════════════════════════════════════

/**
 * Build a fully-degraded context. Used by the trading layer in two
 * cases:
 *
 *   1. Phase 0: bridge service does not exist yet, so every verdict
 *      runs against this empty context. Trading produces a verdict
 *      from TA + Exchange only.
 *   2. Phase 1+: bridge call failed entirely (timeout, exception).
 *      Trading falls back to TA + Exchange only and logs the
 *      degraded reason.
 *
 * IMPORTANT: this function MUST NOT invent confidence. All blocks are
 * `null`, all health flags are `false`.
 */
export function emptyTradingMarketContext(symbol: string): TradingMarketContext {
  return {
    symbol,
    ts: new Date().toISOString(),
    fractal: null,
    sentiment: null,
    onchain: null,
    bridgeHealth: {
      fractal_ok: false,
      sentiment_ok: false,
      onchain_ok: false,
      fractal_ms: 0,
      sentiment_ms: 0,
      onchain_ms: 0,
      reasons: {
        fractal: 'bridge_not_implemented',
        sentiment: 'bridge_not_implemented',
        onchain: 'bridge_not_implemented',
      },
    },
    contractVersion: 'v0',
  };
}

/**
 * Type guard — returns true if at least one external sensor delivered
 * a non-null block. Useful for telling the trading layer "it is worth
 * folding bridge data into the verdict" vs "skip bridge entirely".
 */
export function hasAnyBridgeSignal(ctx: TradingMarketContext): boolean {
  return ctx.fractal !== null || ctx.sentiment !== null || ctx.onchain !== null;
}
