/**
 * Trade Setup Generator — Entry/Stop/TP Logic
 * =============================================
 * 
 * Extracts actionable trade setups from:
 * - render_plan (structure, levels, liquidity)
 * - confluence (bias, strength)
 * 
 * Returns:
 * - Entry zone
 * - Stop loss
 * - Take profit targets (TP1, TP2)
 * - Risk/Reward ratio
 */

/**
 * Build trade setup from render_plan and confluence
 * @param {Object} rp - render_plan from backend
 * @param {Object} confluence - confluence analysis
 * @returns {Object} trade setup
 */
export function buildTradeSetup(rp, confluence) {
  if (!rp || !confluence) {
    return {
      valid: false,
      reason: 'No data available',
    };
  }

  const bias = confluence.bias;
  const strength = confluence.strength;

  // Only generate setup for clear bias
  if (bias === 'neutral') {
    return {
      valid: false,
      reason: 'Neutral market - no clear direction',
    };
  }

  const levels = rp.levels || [];
  const swings = rp.structure?.swings || [];
  const liquidity = rp.liquidity || {};
  const currentPrice = rp.market_state?.current_price;

  if (!levels.length && !swings.length) {
    return {
      valid: false,
      reason: 'Not enough structure/levels data',
    };
  }

  // Determine if bullish or bearish setup
  const isBullish = bias === 'bullish' || bias === 'lean_bullish';
  const isBearish = bias === 'bearish' || bias === 'lean_bearish';

  // ════════════════════════════════════════
  // LONG SETUP
  // ════════════════════════════════════════
  if (isBullish) {
    // Find nearest support for entry
    const supports = levels
      .filter(l => l.type === 'support')
      .sort((a, b) => b.price - a.price); // Highest support first
    
    // Find last swing low for stop
    const swingLows = swings
      .filter(s => s.type === 'LL' || s.type === 'HL' || s.type === 'L')
      .sort((a, b) => b.price - a.price); // Highest low first
    
    // Find resistance for targets
    const resistances = levels
      .filter(l => l.type === 'resistance')
      .sort((a, b) => a.price - b.price); // Lowest resistance first
    
    // Get BSL (Buy-Side Liquidity) for extended targets
    const bsl = liquidity.bsl || [];
    
    if (!supports.length && !swingLows.length) {
      return {
        valid: false,
        reason: 'No support levels for LONG entry',
      };
    }

    // Calculate entry, stop, targets
    const entry = supports[0]?.price || swingLows[0]?.price || currentPrice;
    const stopBase = swingLows[0]?.price || entry * 0.97;
    const stop = stopBase * 0.995; // 0.5% below swing low
    
    const range = entry - stop;
    if (range <= 0) {
      return {
        valid: false,
        reason: 'Invalid entry/stop calculation',
      };
    }

    // Calculate targets based on R:R
    const tp1 = resistances[0]?.price || entry + range * 1.5;
    const tp2 = resistances[1]?.price || bsl[0]?.price || entry + range * 2.5;
    const tp3 = bsl[0]?.price || entry + range * 4;

    // Entry zone (0.3% range around entry)
    const entryZone = {
      low: entry * 0.997,
      high: entry * 1.003,
    };

    // Risk/Reward
    const rr1 = ((tp1 - entry) / range).toFixed(2);
    const rr2 = ((tp2 - entry) / range).toFixed(2);

    return {
      valid: true,
      type: 'LONG',
      direction: 'bullish',
      entry,
      stop,
      tp1,
      tp2,
      tp3,
      entryZone,
      riskReward: {
        tp1: rr1,
        tp2: rr2,
      },
      risk: range,
      confidence: strength,
      reason: `Bullish bias with support at ${entry.toFixed(0)}`,
    };
  }

  // ════════════════════════════════════════
  // SHORT SETUP
  // ════════════════════════════════════════
  if (isBearish) {
    // Find nearest resistance for entry
    const resistances = levels
      .filter(l => l.type === 'resistance')
      .sort((a, b) => a.price - b.price); // Lowest resistance first
    
    // Find last swing high for stop
    const swingHighs = swings
      .filter(s => s.type === 'HH' || s.type === 'LH' || s.type === 'H')
      .sort((a, b) => a.price - b.price); // Lowest high first
    
    // Find support for targets
    const supports = levels
      .filter(l => l.type === 'support')
      .sort((a, b) => b.price - a.price); // Highest support first
    
    // Get SSL (Sell-Side Liquidity) for extended targets
    const ssl = liquidity.ssl || [];
    
    if (!resistances.length && !swingHighs.length) {
      return {
        valid: false,
        reason: 'No resistance levels for SHORT entry',
      };
    }

    // Calculate entry, stop, targets
    const entry = resistances[0]?.price || swingHighs[0]?.price || currentPrice;
    const stopBase = swingHighs[0]?.price || entry * 1.03;
    const stop = stopBase * 1.005; // 0.5% above swing high
    
    const range = stop - entry;
    if (range <= 0) {
      return {
        valid: false,
        reason: 'Invalid entry/stop calculation',
      };
    }

    // Calculate targets based on R:R
    const tp1 = supports[0]?.price || entry - range * 1.5;
    const tp2 = supports[1]?.price || ssl[0]?.price || entry - range * 2.5;
    const tp3 = ssl[0]?.price || entry - range * 4;

    // Entry zone (0.3% range around entry)
    const entryZone = {
      low: entry * 0.997,
      high: entry * 1.003,
    };

    // Risk/Reward
    const rr1 = ((entry - tp1) / range).toFixed(2);
    const rr2 = ((entry - tp2) / range).toFixed(2);

    return {
      valid: true,
      type: 'SHORT',
      direction: 'bearish',
      entry,
      stop,
      tp1,
      tp2,
      tp3,
      entryZone,
      riskReward: {
        tp1: rr1,
        tp2: rr2,
      },
      risk: range,
      confidence: strength,
      reason: `Bearish bias with resistance at ${entry.toFixed(0)}`,
    };
  }

  return {
    valid: false,
    reason: 'Unable to determine setup direction',
  };
}

export default {
  buildTradeSetup,
};
