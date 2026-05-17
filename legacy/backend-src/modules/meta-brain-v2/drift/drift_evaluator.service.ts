/**
 * META BRAIN V2 — DRIFT EVALUATOR
 * =================================
 *
 * Detects module degradation at Meta Brain level.
 *
 * Three drift components:
 *   1. Performance drift — hitRate deviation from baseline
 *   2. Signal drift     — score/confidence distribution shift
 *   3. Coverage drift   — drop/timeout frequency
 *
 * Composite: driftScore = 0.6*perf + 0.3*signal + 0.1*coverage
 * Penalty:   driftPenalty = exp(-2 * driftScore)
 *
 * Status: OK (< 0.2), WATCH (0.2–0.5), DRIFT (> 0.5)
 */

import { getRecentRuns, MetaBrainRunDoc } from '../runs/meta_brain_runs.repo.js';
import { getModulePerformance } from '../performance/performance.repo.js';
import {
  DriftStateDoc,
  saveDriftState,
  appendDriftHistory,
  getAllDriftStates,
} from './drift.repo.js';
import { getProviderKeys } from '../registry/providers.registry.js';

// ═══════════════════════════════════════════════════════════
// CONFIG
// ═══════════════════════════════════════════════════════════

/** Minimum runs needed to compute drift (otherwise skip) */
const MIN_RUNS = 5;

/** Baseline hitRate (coin flip) */
const BASELINE_HITRATE = 0.50;

/** Weight composition */
const PERF_WEIGHT = 0.6;
const SIGNAL_WEIGHT = 0.3;
const COVERAGE_WEIGHT = 0.1;

// ═══════════════════════════════════════════════════════════
// CORE
// ═══════════════════════════════════════════════════════════

export interface DriftEvalResult {
  evaluated: string[];
  skipped: string[];
  states: DriftStateDoc[];
}

/**
 * Evaluate drift for all providers on a given asset+horizon.
 */
export async function evaluateDrift(
  asset: string,
  horizonDays: number,
  runsLimit: number = 60
): Promise<DriftEvalResult> {
  const runs = await getRecentRuns(asset, horizonDays, runsLimit);
  const providerKeys = getProviderKeys();
  const evaluated: string[] = [];
  const skipped: string[] = [];
  const states: DriftStateDoc[] = [];
  const nowTs = Date.now();
  const dateBucket = new Date(nowTs).toISOString().slice(0, 10);

  for (const moduleId of providerKeys) {
    if (runs.length < MIN_RUNS) {
      skipped.push(`${moduleId}: not enough runs (${runs.length}/${MIN_RUNS})`);
      continue;
    }

    // 1. Performance drift
    const perfDrift = await computePerfDrift(moduleId, asset, horizonDays);

    // 2. Signal drift
    const signalDrift = computeSignalDrift(moduleId, runs);

    // 3. Coverage drift
    const coverageDrift = computeCoverageDrift(moduleId, runs);

    // Composite
    const driftScore = Math.min(1, Math.max(0,
      PERF_WEIGHT * perfDrift.score +
      SIGNAL_WEIGHT * signalDrift.score +
      COVERAGE_WEIGHT * coverageDrift.score
    ));

    const penalty = Math.exp(-2 * driftScore);

    let status: 'OK' | 'WATCH' | 'DRIFT' = 'OK';
    if (driftScore > 0.5) status = 'DRIFT';
    else if (driftScore > 0.2) status = 'WATCH';

    // Explain (top reasons)
    const explain: string[] = [];
    if (perfDrift.reason) explain.push(perfDrift.reason);
    if (signalDrift.reason) explain.push(signalDrift.reason);
    if (coverageDrift.reason) explain.push(coverageDrift.reason);

    const state: DriftStateDoc = {
      moduleId,
      asset,
      horizonDays,
      driftScore,
      perfDrift: perfDrift.score,
      signalDrift: signalDrift.score,
      coverageDrift: coverageDrift.score,
      penalty,
      status,
      explain: explain.slice(0, 3),
      updatedAt: nowTs,
    };

    await saveDriftState(state);
    await appendDriftHistory({
      moduleId,
      asset,
      horizonDays,
      dateBucket,
      driftScore,
      penalty,
      status,
      createdAt: nowTs,
    });

    states.push(state);
    evaluated.push(moduleId);
  }

  return { evaluated, skipped, states };
}

// ═══════════════════════════════════════════════════════════
// DRIFT COMPONENTS
// ═══════════════════════════════════════════════════════════

interface DriftComponent {
  score: number;   // [0..1]
  reason: string;
}

/**
 * Performance drift: deviation of hitRate from baseline.
 */
async function computePerfDrift(
  moduleId: string,
  asset: string,
  horizonDays: number
): Promise<DriftComponent> {
  const perf = await getModulePerformance(moduleId, asset, horizonDays);

  if (!perf || perf.samples < 10) {
    return { score: 0, reason: '' }; // Not enough data → no penalty
  }

  // How far below baseline?
  const deviation = Math.max(0, BASELINE_HITRATE - perf.hitRate);
  // Normalize: 0.5 deviation (0% hitRate) → 1.0 drift
  const score = Math.min(1, deviation / 0.5);

  const reason = score > 0.1
    ? `${moduleId} hitRate=${(perf.hitRate * 100).toFixed(0)}% (baseline=${(BASELINE_HITRATE * 100).toFixed(0)}%)`
    : '';

  return { score, reason };
}

/**
 * Signal drift: unusual score/confidence distribution.
 * Checks if a module became "stuck" on one direction or if confidence collapsed.
 */
function computeSignalDrift(
  moduleId: string,
  runs: MetaBrainRunDoc[]
): DriftComponent {
  const moduleSignals = runs
    .map(r => r.signals.find(s => s.moduleId === moduleId))
    .filter(Boolean) as MetaBrainRunDoc['signals'];

  if (moduleSignals.length < MIN_RUNS) {
    return { score: 0, reason: '' };
  }

  // Check direction entropy
  const dirCounts: Record<string, number> = { LONG: 0, SHORT: 0, NEUTRAL: 0 };
  let confSum = 0;
  let scoreSum = 0;

  for (const sig of moduleSignals) {
    dirCounts[sig.direction] = (dirCounts[sig.direction] || 0) + 1;
    confSum += sig.confidence;
    scoreSum += Math.abs(sig.score);
  }

  const n = moduleSignals.length;
  const maxDirRatio = Math.max(dirCounts.LONG, dirCounts.SHORT, dirCounts.NEUTRAL) / n;
  const avgConf = confSum / n;

  // Drift signals:
  // - High direction concentration (>85% one direction) = stuck
  // - Very low confidence average (<0.3) = unreliable
  let score = 0;
  const reasons: string[] = [];

  if (maxDirRatio > 0.85) {
    score += 0.5; // Heavily biased direction
    reasons.push(`${moduleId} stuck: ${(maxDirRatio * 100).toFixed(0)}% same direction`);
  }

  if (avgConf < 0.3) {
    score += 0.5; // Very low confidence
    reasons.push(`${moduleId} low confidence: avg=${avgConf.toFixed(2)}`);
  }

  return { score: Math.min(1, score), reason: reasons.join('; ') };
}

/**
 * Coverage drift: how often the module is dropped/unavailable.
 */
function computeCoverageDrift(
  moduleId: string,
  runs: MetaBrainRunDoc[]
): DriftComponent {
  const totalRuns = runs.length;
  if (totalRuns < MIN_RUNS) return { score: 0, reason: '' };

  let dropCount = 0;
  for (const run of runs) {
    const isDropped = run.droppedModules.some(d => d.module === moduleId);
    const isPresent = run.signals.some(s => s.moduleId === moduleId);
    if (isDropped || !isPresent) dropCount++;
  }

  const dropRate = dropCount / totalRuns;
  // 50%+ drops → full drift
  const score = Math.min(1, dropRate / 0.5);

  const reason = score > 0.1
    ? `${moduleId} dropped ${dropCount}/${totalRuns} runs (${(dropRate * 100).toFixed(0)}%)`
    : '';

  return { score, reason };
}
