/**
 * COGNITIVE LABEL TRANSFORMER  ·  PHASE X · ITERATION 3A · M-05
 *
 * Static lifecycle labels are dead UI tokens.  Cognitive labels are
 * continuous emergence states — the AI is doing something right now,
 * not sitting in a category.
 *
 * NOT used: WATCHING, BUILDING, READY, AVOIDING, SUPPRESSED.
 *     Used: emergence verbs that imply ongoing perception.
 */

export type CognitiveState =
  | 'OBSERVING'
  | 'STRUCTURING'
  | 'ALIGNING'
  | 'BECOMING_ACTIONABLE'
  | 'DEPLOYED'
  | 'COLLAPSING'
  | 'SUPPRESSED'
  | 'COOLING';

export type LegacyFlowState =
  | 'WATCHING' | 'BUILDING' | 'READY' | 'EXECUTED' | 'DISCARDED' | 'AVOIDING';

/** map legacy lifecycle to cognitive emergence state */
export function toCognitive(flow: LegacyFlowState, conf: number): CognitiveState {
  if (flow === 'EXECUTED') return 'DEPLOYED';
  if (flow === 'AVOIDING') return 'SUPPRESSED';
  if (flow === 'DISCARDED') return 'COOLING';
  if (flow === 'READY') return 'BECOMING_ACTIONABLE';
  if (flow === 'BUILDING') return conf >= 0.5 ? 'ALIGNING' : 'STRUCTURING';
  return 'OBSERVING';
}

/** human label that reads as ongoing perception, not a category */
export function cognitiveLabel(s: CognitiveState): string {
  switch (s) {
    case 'OBSERVING':           return 'observing emergence';
    case 'STRUCTURING':         return 'structuring perception';
    case 'ALIGNING':            return 'alignment improving';
    case 'BECOMING_ACTIONABLE': return 'becoming actionable';
    case 'DEPLOYED':            return 'deployed · in flight';
    case 'COLLAPSING':          return 'deployment confidence collapsing';
    case 'SUPPRESSED':          return 'suppressed · capital protected';
    case 'COOLING':             return 'cooling off';
  }
}

/** very short token for compact pills */
export function cognitiveTok(s: CognitiveState): string {
  switch (s) {
    case 'OBSERVING':           return 'OBSERVING';
    case 'STRUCTURING':         return 'STRUCTURING';
    case 'ALIGNING':            return 'ALIGNING';
    case 'BECOMING_ACTIONABLE': return 'BECOMING';
    case 'DEPLOYED':            return 'DEPLOYED';
    case 'COLLAPSING':          return 'COLLAPSING';
    case 'SUPPRESSED':          return 'SUPPRESSED';
    case 'COOLING':             return 'COOLING';
  }
}

/** color token name for theme palette (not a hex) */
export function cognitiveColorKey(s: CognitiveState): string {
  switch (s) {
    case 'OBSERVING':           return 'textMuted';
    case 'STRUCTURING':         return 'textMuted';
    case 'ALIGNING':            return 'warning';
    case 'BECOMING_ACTIONABLE': return 'accent';
    case 'DEPLOYED':            return 'buy';
    case 'COLLAPSING':          return 'sell';
    case 'SUPPRESSED':          return 'sell';
    case 'COOLING':             return 'textMuted';
  }
}

/**
 * Pressure field drift positions (M-04).
 * Maps multi-layer regime + pressure observations into one ambient state.
 */
export type DriftState = 'quiet' | 'unstable' | 'compressing' | 'expanding';

export function deriveDrift(args: {
  pressureLines: string[];
  layers: { layer: string; state: string; tone: string }[];
}): DriftState {
  const { pressureLines, layers } = args;
  const text = pressureLines.join(' ').toLowerCase();
  const vol = layers.find((l) => l.layer === 'Volatility')?.state || '';
  const mom = layers.find((l) => l.layer === 'Momentum')?.state || '';
  const sen = layers.find((l) => l.layer === 'Sentiment')?.state || '';

  if (/flip|unstable|liquidation|overheated|crowded/i.test(text)) return 'unstable';
  if (vol === 'EXPANDING' || mom === 'STRONG' || sen === 'EUPHORIC') return 'expanding';
  if (vol === 'COMPRESSED' || /suppressed|building/i.test(text))    return 'compressing';
  return 'quiet';
}

export const DRIFT_ORDER: DriftState[] = ['quiet', 'compressing', 'unstable', 'expanding'];
export function driftIndex(s: DriftState): number {
  return Math.max(0, DRIFT_ORDER.indexOf(s));
}
export function driftDescription(s: DriftState): string {
  switch (s) {
    case 'quiet':       return 'field calm · no measurable pressure forming';
    case 'compressing': return 'energy storing · no release direction yet';
    case 'unstable':    return 'directional polarity flipping · low trust';
    case 'expanding':   return 'volatility releasing · regime opening up';
  }
}

/**
 * CAPITAL DRIFT — Portfolio's living posture (Iteration 3B).
 * Shows that money itself has a state, not just the AI.
 */
export type CapitalDriftState = 'exposed' | 'protected' | 'waiting' | 'idle';

export const CAPITAL_DRIFT_ORDER: CapitalDriftState[] =
  ['idle', 'waiting', 'protected', 'exposed'];

export function capitalDriftIndex(s: CapitalDriftState): number {
  return Math.max(0, CAPITAL_DRIFT_ORDER.indexOf(s));
}

export function capitalDriftDescription(s: CapitalDriftState): string {
  switch (s) {
    case 'idle':      return 'capital intentionally idle · awaiting asymmetry';
    case 'waiting':   return 'portfolio waiting for asymmetry · no pressure to deploy';
    case 'protected': return 'exposure suppressed · capital moving to cash';
    case 'exposed':   return 'capital deployed · directional bet active';
  }
}

export function deriveCapitalDrift(args: {
  longUSD: number;
  shortUSD: number;
  cashUSD: number;
  suppressedCount: number;
  positions: number;
}): CapitalDriftState {
  const { longUSD, shortUSD, cashUSD, suppressedCount, positions } = args;
  const total = longUSD + shortUSD + cashUSD;
  const deployedRatio = total > 0 ? (longUSD + shortUSD) / total : 0;

  if (positions === 0 && suppressedCount > 0) return 'protected';
  if (positions === 0)                        return 'idle';
  if (deployedRatio < 0.15)                   return 'waiting';
  if (deployedRatio < 0.4)                    return 'protected';
  return 'exposed';
}

/**
 * INTENTION DRIFT — Command's progression of mental state.
 *
 *   DORMANT  → OBSERVING  → BUILDING  → READY
 *
 * Same primitive as a lifecycle, just narrated as intent shifts.
 */
export type IntentionState = 'DORMANT' | 'OBSERVING' | 'BUILDING' | 'READY';

export const INTENTION_ORDER: IntentionState[] =
  ['DORMANT', 'OBSERVING', 'BUILDING', 'READY'];

export function intentionIndex(s: IntentionState): number {
  return Math.max(0, INTENTION_ORDER.indexOf(s));
}

export function intentionVerb(s: IntentionState): string {
  switch (s) {
    case 'DORMANT':   return 'waiting for first signal · capital still';
    case 'OBSERVING': return 'sensing field · no commitment yet';
    case 'BUILDING':  return 'alignment forming · convictions assembling';
    case 'READY':     return 'gates clearing · deployment window open';
  }
}

/** Map raw readiness model → IntentionState */
export function readinessToIntention(state: string, pct: number): IntentionState {
  const s = String(state || '').toUpperCase();
  if (s === 'READY' || pct >= 0.7)             return 'READY';
  if (s === 'BUILDING' || (pct >= 0.4 && pct < 0.7)) return 'BUILDING';
  if (s === 'DORMANT' || s === 'DEFENSIVE' || pct < 0.2) return 'DORMANT';
  return 'OBSERVING';
}

/**
 * CONVICTION EVOLUTION — verbal arc across RAW → META → FINAL (Iteration 3B).
 * Used by Execution Console.
 */
export type ConvictionVerb =
  | 'strengthening' | 'weakening' | 'collapsed' | 'stabilizing' | 'flipped';

export function convictionVerb(args: {
  rawConf: number | null | undefined;
  finalConf: number | null | undefined;
  rawDir?: string | null;
  finalDir?: string | null;
}): ConvictionVerb {
  const { rawConf, finalConf, rawDir, finalDir } = args;
  if (rawDir && finalDir && rawDir !== finalDir
      && rawDir !== 'HOLD' && finalDir !== 'HOLD'
      && rawDir !== 'WAIT' && finalDir !== 'WAIT') {
    return 'flipped';
  }
  if (rawConf == null || finalConf == null) return 'stabilizing';
  const d = finalConf - rawConf;
  if (finalConf < 0.25 && rawConf >= 0.5) return 'collapsed';
  if (d > 0.06)  return 'strengthening';
  if (d < -0.06) return 'weakening';
  return 'stabilizing';
}

export function convictionVerbColorKey(v: ConvictionVerb): string {
  switch (v) {
    case 'strengthening': return 'buy';
    case 'weakening':     return 'warning';
    case 'collapsed':     return 'sell';
    case 'flipped':       return 'sell';
    case 'stabilizing':   return 'textMuted';
  }
}
