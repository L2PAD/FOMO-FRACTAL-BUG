/**
 * Execution Context Types
 *
 * Context clustering for execution quality analysis.
 * contextKey is the primary key for all clustering/storage.
 */

export type Direction = 'LONG' | 'SHORT';
export type Regime = 'TREND' | 'RANGE' | 'TRANSITION';
export type NarrativePhase = 'EARLY' | 'EXPANDING' | 'SATURATED' | 'EXHAUSTED';
export type VolatilityBucket = 'LOW' | 'MEDIUM' | 'HIGH';
export type ExecutionStyle = 'MARKET' | 'LIMIT' | 'WAIT' | 'STAGGER' | 'FADE_SPIKE' | 'UNKNOWN';

export interface ExecutionContext {
  direction: Direction;
  regime: Regime;
  narrative: NarrativePhase;
  volatilityBucket: VolatilityBucket;
  executionStyle: ExecutionStyle;
}

/**
 * Build a deterministic context key from context components.
 * Format: LONG:TREND:EARLY:HIGH:MARKET
 */
export function buildContextKey(ctx: ExecutionContext): string {
  return `${ctx.direction}:${ctx.regime}:${ctx.narrative}:${ctx.volatilityBucket}:${ctx.executionStyle}`;
}

/**
 * Parse a context key back into ExecutionContext.
 */
export function parseContextKey(key: string): ExecutionContext {
  const [direction, regime, narrative, volatilityBucket, executionStyle] = key.split(':');
  return {
    direction: (direction as Direction) || 'LONG',
    regime: (regime as Regime) || 'RANGE',
    narrative: (narrative as NarrativePhase) || 'EXPANDING',
    volatilityBucket: (volatilityBucket as VolatilityBucket) || 'MEDIUM',
    executionStyle: (executionStyle as ExecutionStyle) || 'UNKNOWN',
  };
}

/**
 * Single execution score entry stored in the context stats.
 */
export interface ExecutionScoreEntry {
  score: number;
  grade: string;
  asset: string;
  marketId: string;
  timestamp: string;
  entryScore: number;
  timingScore: number;
  slippageLeakage: number;
  opportunityCost: number;
  missedMove: number;
  confidence: number;
  edge: number;
  opportunityReason: string;
}

/**
 * Per-context aggregated stats stored in MongoDB.
 */
export interface ContextStats {
  contextKey: string;
  context: ExecutionContext;
  entries: ExecutionScoreEntry[];
  totalCount: number;
  updatedAt: string;
}

/**
 * Style comparison result.
 */
export interface StyleComparison {
  style: ExecutionStyle;
  avgScore: number;
  count: number;
  winRate: number;
  avgLeakage: number;
  missRate: number;
}
