/**
 * useUnifiedTAState — Single Source of Truth for Tech Analysis frontend
 * =====================================================================
 *
 * Backend produces ONE coherent object per timeframe:
 *   tf_map[tf] = {
 *     decision: { bias, confidence, tradeability, ... },   ← TRUTH
 *     render_plan: { structure, patterns, levels, execution, liquidity, ... },
 *     ta_context: { indicators, regime, ... },             ← EXPLANATION
 *     summary, primary_pattern, fib, ...
 *   }
 *
 * Hard rule (Pass 3 honesty):
 *   * `decision.bias` and `decision.confidence` are the ONLY ground truth
 *     for direction/conviction.
 *   * Indicators / structure / patterns are EXPLANATION layers, not separate
 *     opinions. They MUST NOT compute their own bias and contradict the
 *     decision.
 *   * No fabricated fallbacks (no 0.5 magic numbers anywhere).
 *
 * Consumers receive a flat, normalized object so each UI block can render
 * its slice without re-deriving truth.
 */

import { useMemo } from 'react';

/**
 * Build the unified TA state from a single setupData payload.
 *
 * @param {Object} setupData  one TF block from /api/ta-engine/mtf
 * @param {string} tf         canonical timeframe ("4H","1D",...)
 * @returns {Object|null}     unified state or null when no data
 */
export function useUnifiedTAState(setupData, tf) {
  return useMemo(() => {
    if (!setupData) return null;

    const decision = setupData.decision || {};
    const renderPlan = setupData.render_plan || null;
    const taContext = setupData.ta_context || null;
    const summary = setupData.summary || null;

    // ─── 🧠 GROUND TRUTH (decision-only, no recomputation) ────────────
    const bias = decision.bias || 'neutral';
    const confidence = clamp01(decision.confidence);
    const tradeability = decision.tradeability || 'low';
    const indicatorBias = decision.indicator_bias || null;
    const strength = decision.strength || null;
    const alignment = decision.alignment || null;
    const dominantTF = decision.dominant_tf || null;

    // ─── 🔬 EXPLANATION LAYERS (read-only, never override truth) ──────

    // STRUCTURE — geometry of price (HH/HL/LH/LL, BOS/CHOCH)
    const structure = renderPlan?.structure || null;

    // PATTERNS — primary + alternatives
    const patternsBlock = renderPlan?.patterns || null;
    const primaryPattern = patternsBlock?.primary || setupData.primary_pattern || null;
    const alternativePatterns = setupData.alternative_patterns || [];

    // LEVELS — support/resistance (already ranked by backend)
    const levels = renderPlan?.levels || setupData.levels || [];

    // INDICATORS — list of bullish/bearish/neutral signals (NOT a bias source)
    const indicators = taContext?.indicators || null;

    // EXECUTION — trade levels / status (decision-aware on backend)
    const execution = renderPlan?.execution || setupData.execution || null;

    // LIQUIDITY / POI / DISPLACEMENT / CHOCH — Smart Money layer
    const liquidity = renderPlan?.liquidity || setupData.liquidity || null;
    const poi = setupData.poi || null;
    const displacement = setupData.displacement || null;
    const chochValidation = setupData.choch_validation || null;

    // FIBONACCI
    const fib = setupData.fib || setupData.fibonacci || null;

    // ─── 📈 ANALYTIC DERIVATIVES (from decision-aware summary block) ──
    const contextFit = summary?.context_fit ?? setupData.context_fit ?? null;
    const tradeable = summary?.tradeable ?? setupData.tradeable ?? null;
    const probability = summary?.probability_v3 ?? setupData.probability_v3 ?? null;
    const historical = summary?.historical ?? setupData.historical ?? null;
    const executionPlan = summary?.execution_plan ?? setupData.execution_plan ?? null;
    const regimeDrift = summary?.regime_drift ?? setupData.regime_drift ?? null;
    const context = summary?.context ?? setupData.context ?? null;

    // ─── 📊 INDICATOR EXPLANATION (decompose, NOT a separate vote) ────
    // Goal: tell the user WHICH indicators agree with decision.bias and
    // which dissent — without claiming a different bias.
    const indicatorExplanation = explainIndicators(taContext?.indicators, bias);

    // ─── 🎯 CONFIDENCE BREAKDOWN (real numbers from decision only) ────
    // No 0.5/0.6/0.8 magic numbers. We expose only what backend gave us.
    const confidenceBreakdown = buildConfidenceBreakdown(decision, primaryPattern);

    return {
      // ─── meta ──────────────────────────────────────────────────────
      symbol: setupData.symbol,
      timeframe: setupData.timeframe || tf,
      currentPrice: setupData.current_price ?? renderPlan?.market_state?.current_price ?? null,
      timestamp: setupData.timestamp,

      // ─── 🧠 GROUND TRUTH (read by every UI block) ──────────────────
      bias,                         // 'bullish' | 'bearish' | 'neutral'
      confidence,                   // 0..1, honest
      tradeability,                 // 'high' | 'medium' | 'low'
      indicatorBias,                // optional sub-bias of indicators (string only)
      strength,                     // 'strong' | 'moderate' | 'weak' | null
      alignment,                    // 'aligned' | 'mixed' | null
      dominantTF,                   // 'macro' | 'mid' | 'short' | null

      // ─── 🔬 EXPLANATION LAYERS ─────────────────────────────────────
      structure,
      primaryPattern,
      alternativePatterns,
      levels,
      indicators,
      indicatorExplanation,         // { supporting, dissenting, neutral, summary }
      execution,
      liquidity,
      poi,
      displacement,
      chochValidation,
      fib,

      // ─── 📈 ANALYTIC DERIVATIVES ───────────────────────────────────
      contextFit,
      tradeable,
      probability,
      historical,
      executionPlan,
      regimeDrift,
      context,

      // ─── 🎯 CONFIDENCE BREAKDOWN (no magic numbers) ────────────────
      confidenceBreakdown,

      // ─── ❗ raw payload for niche debug / Deep section ─────────────
      raw: setupData,
    };
  }, [setupData, tf]);
}


// ════════════════════════════════════════════════════════════════════════════
// HELPERS
// ════════════════════════════════════════════════════════════════════════════

function clamp01(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(1, n));
}

/**
 * Decompose indicator signals as EXPLANATION ONLY.
 *
 * Returns { supporting: [...], dissenting: [...], neutral: [...], summary }
 * where "supporting" means "this indicator's direction matches decision.bias".
 *
 * IMPORTANT: This function NEVER returns a `bias` field of its own — it
 * only labels existing signals relative to ground truth.
 */
function explainIndicators(indicators, bias) {
  const signals = (indicators?.signals || []).filter(Boolean);
  if (!signals.length) {
    return { supporting: [], dissenting: [], neutral: [], summary: null };
  }

  const supporting = [];
  const dissenting = [];
  const neutral = [];

  signals.forEach((s) => {
    const dir = String(s.direction || '').toLowerCase();
    const item = {
      name: s.name,
      direction: dir,
      strength: Number(s.strength || 0),
      description: s.description,
      signal_type: s.signal_type,
    };
    if (!dir || dir === 'neutral') {
      neutral.push(item);
      return;
    }
    if (bias === 'neutral') {
      // No truth bias to support → all directional indicators go to neutral bucket
      neutral.push(item);
      return;
    }
    if (dir === bias) {
      supporting.push(item);
    } else {
      dissenting.push(item);
    }
  });

  // Honest summary string — NOT a bias claim, just counts.
  const total = signals.length;
  const summary = `${supporting.length}/${total} indicators support · ${dissenting.length} dissent · ${neutral.length} neutral`;

  return { supporting, dissenting, neutral, summary, total };
}

/**
 * Confidence breakdown — only fields produced by the backend `decision` /
 * pattern objects. No magic 0.5/0.6/0.65/0.8 fillers.
 *
 * Returned object contains only keys that have real numeric values; missing
 * components are simply absent (UI must handle null gracefully).
 */
function buildConfidenceBreakdown(decision, primaryPattern) {
  const out = {};

  // Backend may already provide a ready breakdown
  const cb = decision?.confidence_breakdown;
  if (cb && typeof cb === 'object') {
    Object.entries(cb).forEach(([k, v]) => {
      if (typeof v === 'number' && Number.isFinite(v)) {
        out[k] = clamp01(v);
      }
    });
  }

  // Pattern-level scores (real, when present)
  const scores = primaryPattern?.scores || {};
  ['geometry', 'structure', 'level', 'recency', 'cleanliness', 'touch_score'].forEach((k) => {
    if (typeof scores[k] === 'number' && Number.isFinite(scores[k])) {
      out[k] = clamp01(scores[k]);
    }
  });

  // Aggregate-level honest fields
  if (typeof decision?.confidence === 'number') out.overall = clamp01(decision.confidence);
  if (typeof decision?.confidence_raw === 'number') out.confidence_raw = clamp01(decision.confidence_raw);
  if (typeof decision?.indicator_score === 'number') out.indicator_score = clamp01(decision.indicator_score);
  if (typeof decision?.total_multiplier === 'number') out.total_multiplier = decision.total_multiplier;

  return out;
}

export default useUnifiedTAState;
