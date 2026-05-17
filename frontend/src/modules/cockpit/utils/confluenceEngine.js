/**
 * Confluence Engine — TA Decision Logic
 * =====================================
 * 
 * Transforms raw render_plan data into actionable analysis:
 * - Trend alignment
 * - Structure bias
 * - Liquidity activity
 * - Confluence score
 * - Trade decision
 * 
 * This is the BRAIN of the TA system.
 */

/**
 * Build confluence analysis from render_plan
 * @param {Object} rp - render_plan from backend
 * @returns {Object} confluence analysis
 */
export function buildConfluence(rp) {
  if (!rp) return null;

  let score = 0;
  const signals = [];
  const factors = [];

  // ════════════════════════════════════════
  // 1. TREND ANALYSIS
  // ════════════════════════════════════════
  const trend = rp.market_state?.trend?.toLowerCase();
  const trendStrength = rp.market_state?.trend_strength || 'weak';
  
  if (trend === 'uptrend') {
    const pts = trendStrength === 'strong' ? 3 : trendStrength === 'moderate' ? 2 : 1;
    score += pts;
    signals.push(`Trend: ${trend} (${trendStrength})`);
    factors.push({ name: 'Trend', value: trend, bias: 'bullish', weight: pts });
  } else if (trend === 'downtrend') {
    const pts = trendStrength === 'strong' ? 3 : trendStrength === 'moderate' ? 2 : 1;
    score -= pts;
    signals.push(`Trend: ${trend} (${trendStrength})`);
    factors.push({ name: 'Trend', value: trend, bias: 'bearish', weight: pts });
  } else {
    factors.push({ name: 'Trend', value: 'neutral', bias: 'neutral', weight: 0 });
  }

  // ════════════════════════════════════════
  // 2. STRUCTURE ANALYSIS
  // ════════════════════════════════════════
  const structureBias = rp.structure?.bias?.toLowerCase();
  const swings = rp.structure?.swings || [];
  const bos = rp.structure?.bos;
  const choch = rp.structure?.choch;
  
  if (structureBias === 'bullish') {
    score += 2;
    signals.push('Structure: bullish bias');
    factors.push({ name: 'Structure', value: 'bullish', bias: 'bullish', weight: 2 });
  } else if (structureBias === 'bearish') {
    score -= 2;
    signals.push('Structure: bearish bias');
    factors.push({ name: 'Structure', value: 'bearish', bias: 'bearish', weight: 2 });
  } else {
    factors.push({ name: 'Structure', value: 'neutral', bias: 'neutral', weight: 0 });
  }
  
  // BOS/CHOCH adds extra weight
  if (bos) {
    const bosDir = bos.direction?.toLowerCase();
    if (bosDir === 'bullish') {
      score += 1;
      signals.push('BOS: bullish break');
    } else if (bosDir === 'bearish') {
      score -= 1;
      signals.push('BOS: bearish break');
    }
  }
  
  if (choch) {
    const chochDir = choch.direction?.toLowerCase();
    if (chochDir === 'bullish') {
      score += 2;
      signals.push('CHOCH: bullish shift!');
    } else if (chochDir === 'bearish') {
      score -= 2;
      signals.push('CHOCH: bearish shift!');
    }
  }

  // ════════════════════════════════════════
  // 3. LIQUIDITY ANALYSIS
  // ════════════════════════════════════════
  const sweeps = rp.liquidity?.sweeps || [];
  const bsl = rp.liquidity?.bsl || [];
  const ssl = rp.liquidity?.ssl || [];
  
  let liquidityBias = 'neutral';
  let liquidityScore = 0;
  
  sweeps.forEach(s => {
    const dir = s.direction?.toLowerCase();
    if (dir === 'bullish') {
      liquidityScore += 1;
      signals.push('Liquidity sweep: bullish');
    } else if (dir === 'bearish') {
      liquidityScore -= 1;
      signals.push('Liquidity sweep: bearish');
    }
  });
  
  score += liquidityScore;
  
  if (liquidityScore > 0) {
    liquidityBias = 'bullish';
  } else if (liquidityScore < 0) {
    liquidityBias = 'bearish';
  }
  
  factors.push({ 
    name: 'Liquidity', 
    value: sweeps.length > 0 ? `${sweeps.length} sweeps` : 'quiet', 
    bias: liquidityBias, 
    weight: Math.abs(liquidityScore) 
  });

  // ════════════════════════════════════════
  // 4. INDICATOR CONFLUENCE
  // ════════════════════════════════════════
  const overlays = rp.indicators?.overlays || [];
  const hasEMA = overlays.some(o => o.id?.includes('ema'));
  
  if (hasEMA) {
    factors.push({ name: 'EMA', value: 'active', bias: 'neutral', weight: 1 });
  }

  // ════════════════════════════════════════
  // 5. EXECUTION STATUS
  // ════════════════════════════════════════
  const execution = rp.execution;
  const executionValid = execution?.valid || execution?.status === 'valid';
  
  if (executionValid) {
    const execDir = execution.direction?.toLowerCase();
    if (execDir === 'long') {
      score += 2;
      signals.push('Execution: LONG setup valid');
    } else if (execDir === 'short') {
      score -= 2;
      signals.push('Execution: SHORT setup valid');
    }
  }

  // ════════════════════════════════════════
  // 6. COMPUTE FINAL RESULT
  // ════════════════════════════════════════
  let bias = 'neutral';
  if (score >= 3) bias = 'bullish';
  else if (score <= -3) bias = 'bearish';
  else if (score > 0) bias = 'lean_bullish';
  else if (score < 0) bias = 'lean_bearish';

  let strength = 'low';
  const absScore = Math.abs(score);
  if (absScore >= 6) strength = 'high';
  else if (absScore >= 4) strength = 'medium';

  // Decision
  let decision = 'wait';
  let decisionReason = 'No clear confluence';
  
  if (bias === 'bullish' && strength !== 'low') {
    decision = 'long';
    decisionReason = 'Bullish confluence aligns';
  } else if (bias === 'bearish' && strength !== 'low') {
    decision = 'short';
    decisionReason = 'Bearish confluence aligns';
  } else if (bias === 'lean_bullish') {
    decision = 'watch_long';
    decisionReason = 'Leaning bullish, needs confirmation';
  } else if (bias === 'lean_bearish') {
    decision = 'watch_short';
    decisionReason = 'Leaning bearish, needs confirmation';
  }

  return {
    bias,
    strength,
    score,
    signals,
    factors,
    decision,
    decisionReason,
    summary: buildSummary(bias, strength, signals.length),
    // Raw data for debug
    raw: {
      trend,
      structureBias,
      sweepsCount: sweeps.length,
      executionValid,
    }
  };
}

/**
 * Build human-readable summary
 */
function buildSummary(bias, strength, signalCount) {
  const biasText = {
    bullish: 'Bullish',
    bearish: 'Bearish',
    lean_bullish: 'Leaning Bullish',
    lean_bearish: 'Leaning Bearish',
    neutral: 'Neutral',
  };
  
  const strengthText = {
    high: 'strong',
    medium: 'moderate',
    low: 'weak',
  };
  
  if (bias === 'neutral') {
    return 'No clear directional bias';
  }
  
  return `${biasText[bias]} confluence (${strengthText[strength]})`;
}

/**
 * Get layer visibility based on mode
 * @param {string} mode - 'auto', 'classic', 'smart', 'minimal'
 * @returns {Object} visibility settings
 */
export function getLayerVisibility(mode) {
  const base = {
    structure: true,
    levels: true,
    liquidity: true,
    indicators: true,
    execution: true,
    patterns: true,
    poi: true,
    sweeps: true,
  };
  
  switch (mode) {
    case 'minimal':
      return {
        ...base,
        structure: false,
        liquidity: false,
        indicators: false,
        patterns: false,
        poi: false,
        sweeps: false,
      };
    
    case 'classic':
      return {
        ...base,
        liquidity: false,
        poi: false,
        sweeps: false,
      };
    
    case 'smart':
      return {
        ...base,
        structure: false,
        indicators: false,
        patterns: false,
      };
    
    case 'auto':
    default:
      return base;
  }
}

/**
 * Build trade setup from render_plan
 * @param {Object} rp - render_plan
 * @param {Object} confluence - confluence analysis
 * @returns {Object|null} trade setup
 */
export function buildTradeSetup(rp, confluence) {
  if (!rp || !confluence || confluence.strength === 'low') {
    return null;
  }
  
  const execution = rp.execution;
  if (!execution?.valid && execution?.status !== 'valid') {
    return null;
  }
  
  const levels = rp.levels || [];
  const currentPrice = rp.market_state?.current_price;
  
  if (!currentPrice) return null;
  
  // Find nearest support/resistance
  const supports = levels.filter(l => l.type === 'support' && l.price < currentPrice);
  const resistances = levels.filter(l => l.type === 'resistance' && l.price > currentPrice);
  
  const nearestSupport = supports.length > 0 
    ? supports.reduce((a, b) => b.price > a.price ? b : a) 
    : null;
  const nearestResistance = resistances.length > 0 
    ? resistances.reduce((a, b) => b.price < a.price ? b : a) 
    : null;
  
  // Calculate entry/stop/targets based on direction
  const direction = confluence.decision === 'long' ? 'long' : 
                   confluence.decision === 'short' ? 'short' : null;
  
  if (!direction) return null;
  
  let entry, stop, tp1, tp2;
  
  if (direction === 'long') {
    entry = execution.entry || currentPrice;
    stop = execution.stop || nearestSupport?.price || entry * 0.97;
    const range = entry - stop;
    tp1 = execution.tp1 || entry + range * 1.5;
    tp2 = execution.tp2 || entry + range * 2.5;
  } else {
    entry = execution.entry || currentPrice;
    stop = execution.stop || nearestResistance?.price || entry * 1.03;
    const range = stop - entry;
    tp1 = execution.tp1 || entry - range * 1.5;
    tp2 = execution.tp2 || entry - range * 2.5;
  }
  
  return {
    valid: true,  // Добавляем флаг valid для SetupOverlay
    type: direction === 'long' ? 'LONG' : 'SHORT',
    direction,
    entry,
    stop,
    tp1,
    tp2,
    riskReward: Math.abs((tp1 - entry) / (entry - stop)).toFixed(2),
    confidence: confluence.strength,
  };
}

export default {
  buildConfluence,
  getLayerVisibility,
  buildTradeSetup,
};
