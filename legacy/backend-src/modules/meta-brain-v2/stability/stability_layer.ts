import { AggregationResult } from '../aggregator/signal_aggregator.js';
import { getState, saveState } from './meta_brain_state.service.js';

type Direction = 'LONG' | 'SHORT' | 'NEUTRAL';
const DEFAULT_COOLDOWN_MS = 2 * 60 * 60 * 1000;

export interface StabilityResult {
  finalVerdict: Direction;
  finalScore: number;
  rawVerdict: Direction;
  rawScore: number;
  verdictChanged: boolean;
  stabilityApplied: boolean;
  reason: string;
  cooldownActive: boolean;
  cooldownUntilTs: number | null;
  cooldownMs: number;
  thresholdsUsed: { enter: number; exit: number };
  previousVerdict: Direction | null;
}

export async function applyStability(agg: AggregationResult, nowTs: number = Date.now()): Promise<StabilityResult> {
  const policy = agg.policy;
  const prevState = await getState(agg.asset, agg.horizonDays);
  const cooldownMs = policy.cooldown[String(agg.horizonDays)] ?? DEFAULT_COOLDOWN_MS;
  const thresholds = policy.thresholds;

  if (agg.metaStatus === 'INSUFFICIENT') {
    const kept = (prevState?.lastVerdict as Direction) || 'NEUTRAL';
    return { finalVerdict: kept, finalScore: prevState?.lastScore ?? 0, rawVerdict: agg.rawVerdict, rawScore: agg.rawScore, verdictChanged: false, stabilityApplied: true, reason: 'INSUFFICIENT coverage - verdict held', cooldownActive: false, cooldownUntilTs: null, cooldownMs, thresholdsUsed: thresholds, previousVerdict: (prevState?.lastVerdict as Direction) ?? null };
  }

  const rawScore = agg.rawScore;
  const rawVerdict = agg.rawVerdict;
  const prevVerdict = (prevState?.lastVerdict as Direction) ?? 'NEUTRAL';
  const cooldownUntilTs = prevState?.cooldownUntilTs ?? 0;

  if (cooldownUntilTs > nowTs) {
    return { finalVerdict: prevVerdict, finalScore: prevState?.lastScore ?? rawScore, rawVerdict, rawScore, verdictChanged: false, stabilityApplied: true, reason: 'Cooldown active until ' + new Date(cooldownUntilTs).toISOString(), cooldownActive: true, cooldownUntilTs, cooldownMs, thresholdsUsed: thresholds, previousVerdict: prevVerdict };
  }

  const finalVerdict = applyHysteresis(rawScore, prevVerdict, thresholds.enter, thresholds.exit);
  const verdictChanged = finalVerdict !== prevVerdict;
  let newCooldownUntilTs = cooldownUntilTs;
  let reason: string;

  if (verdictChanged) {
    newCooldownUntilTs = nowTs + cooldownMs;
    reason = 'Verdict flipped: ' + prevVerdict + ' -> ' + finalVerdict + ' (cooldown ' + (cooldownMs / 60000) + 'min, ' + agg.regime + ' policy)';
  } else {
    reason = 'Verdict held at ' + finalVerdict + ' (' + agg.regime + ' hysteresis: enter=' + thresholds.enter + ', exit=' + thresholds.exit + ')';
  }

  await saveState({ asset: agg.asset.toUpperCase(), horizon: agg.horizonDays, lastVerdict: finalVerdict, lastScore: rawScore, lastRawScore: rawScore, lastUpdatedTs: nowTs, cooldownUntilTs: newCooldownUntilTs });

  return { finalVerdict, finalScore: rawScore, rawVerdict, rawScore, verdictChanged, stabilityApplied: verdictChanged || finalVerdict !== rawVerdict, reason, cooldownActive: false, cooldownUntilTs: verdictChanged ? newCooldownUntilTs : null, cooldownMs, thresholdsUsed: thresholds, previousVerdict: prevVerdict };
}

function applyHysteresis(rawScore: number, prevVerdict: Direction, enterThreshold: number, exitThreshold: number): Direction {
  switch (prevVerdict) {
    case 'LONG':
      if (rawScore < exitThreshold) { return rawScore <= -enterThreshold ? 'SHORT' : 'NEUTRAL'; }
      return 'LONG';
    case 'SHORT':
      if (rawScore > -exitThreshold) { return rawScore >= enterThreshold ? 'LONG' : 'NEUTRAL'; }
      return 'SHORT';
    default:
      if (rawScore >= enterThreshold) return 'LONG';
      if (rawScore <= -enterThreshold) return 'SHORT';
      return 'NEUTRAL';
  }
}
