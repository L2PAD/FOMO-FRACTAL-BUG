/**
 * NarrativeEngine — Build market story from data
 * ================================================
 * 
 * Transforms raw market mechanics data into a narrative sequence:
 * [1] Liquidity taken → [2] Impulse → [3] VALID CHOCH → [4] Supply zone → [5] SHORT setup
 * 
 * Rules:
 * - Max 5 events
 * - Only show if there's a valid chain (sweep + displacement + POI)
 * - Entry only if setup is valid
 */

/**
 * Build narrative events from market data
 * 
 * @param {Object} data - { liquidity, displacement, chochValidation, poi, decision, tradeSetup }
 * @returns {Array} - Sorted array of narrative events
 */
export function buildNarrative(data) {
  const { liquidity, displacement, chochValidation, poi, decision, tradeSetup } = data;
  
  const events = [];
  
  // 1. LIQUIDITY SWEEP
  const sweeps = liquidity?.sweeps || [];
  const lastSweep = sweeps.length > 0 ? sweeps[0] : null; // Most recent/strongest
  
  if (lastSweep) {
    const isBSL = lastSweep.type === 'buy_side_sweep';
    events.push({
      type: 'liquidity_sweep',
      subtype: lastSweep.type,
      label: isBSL ? '① BSL Swept' : '① SSL Swept',
      description: isBSL 
        ? 'Buy-side liquidity taken → bearish signal'
        : 'Sell-side liquidity taken → bullish signal',
      time: lastSweep.time,
      price: lastSweep.sweep_price,
      direction: isBSL ? 'bearish' : 'bullish',
      priority: 1,
      color: isBSL ? '#ef4444' : '#22c55e',
      markerPosition: isBSL ? 'aboveBar' : 'belowBar',
      shape: isBSL ? 'arrowDown' : 'arrowUp',
    });
  }
  
  // 2. DISPLACEMENT (IMPULSE)
  const dispEvents = displacement?.events || [];
  const recentDisplacement = displacement?.recent_displacement;
  const lastImpulse = displacement?.last_impulse;
  
  if (lastImpulse && lastImpulse.strength >= 2.0) {
    const isBearish = lastImpulse.direction === 'bearish';
    events.push({
      type: 'displacement',
      subtype: lastImpulse.direction,
      label: isBearish ? '② Bearish Impulse' : '② Bullish Impulse',
      description: `Strong ${lastImpulse.direction} move (${lastImpulse.range_pct}%)`,
      time: lastImpulse.end_time || lastImpulse.start_time,
      price: null, // Will be calculated from candles
      direction: lastImpulse.direction,
      priority: 2,
      color: isBearish ? '#ef4444' : '#22c55e',
      markerPosition: isBearish ? 'aboveBar' : 'belowBar',
      shape: isBearish ? 'arrowDown' : 'arrowUp',
      strength: lastImpulse.strength,
    });
  }
  
  // 3. CHOCH VALIDATION
  if (chochValidation && chochValidation.event_time) {
    const { is_valid, score, direction, label: chochLabel } = chochValidation;
    
    let statusLabel;
    let statusColor;
    
    if (is_valid) {
      statusLabel = '③ VALID CHOCH';
      statusColor = '#22c55e';
    } else if (score >= 0.45) {
      statusLabel = '③ WEAK CHOCH';
      statusColor = '#f59e0b';
    } else {
      statusLabel = '③ FAKE CHOCH';
      statusColor = '#6b7280';
    }
    
    const isBullish = direction === 'bullish';
    
    events.push({
      type: 'choch',
      subtype: chochLabel,
      label: statusLabel,
      description: `Structure shift ${is_valid ? 'confirmed' : 'unconfirmed'} (score: ${score})`,
      time: chochValidation.event_time,
      price: null,
      direction: direction,
      priority: 3,
      color: statusColor,
      markerPosition: isBullish ? 'belowBar' : 'aboveBar',
      shape: isBullish ? 'arrowUp' : 'arrowDown',
      isValid: is_valid,
      score: score,
    });
  }
  
  // 4. POI (SUPPLY/DEMAND ZONE)
  const activeZones = poi?.active_zones || [];
  const strongestZone = poi?.zones?.[0]; // Already sorted by strength
  
  if (strongestZone && !strongestZone.mitigated) {
    const isSupply = strongestZone.type === 'supply';
    events.push({
      type: 'poi',
      subtype: strongestZone.type,
      label: isSupply ? '④ Supply Zone' : '④ Demand Zone',
      description: `${strongestZone.label} (strength: ${strongestZone.strength})`,
      time: strongestZone.origin_time,
      price: strongestZone.price_mid,
      priceHigh: strongestZone.price_high,
      priceLow: strongestZone.price_low,
      direction: isSupply ? 'bearish' : 'bullish',
      priority: 4,
      color: isSupply ? '#ef4444' : '#22c55e',
      markerPosition: isSupply ? 'aboveBar' : 'belowBar',
      shape: 'circle',
    });
  }
  
  // 5. TRADE SETUP (ENTRY)
  const primarySetup = tradeSetup?.primary;
  const bias = decision?.bias;
  
  if (primarySetup && decision) {
    const isShort = bias === 'bearish';
    const confidence = decision.confidence || 0;
    
    // Only show entry if we have enough confirmation
    const hasNarrative = events.length >= 2; // At least sweep + one more event
    
    if (hasNarrative && confidence >= 0.5) {
      events.push({
        type: 'entry',
        subtype: isShort ? 'short' : 'long',
        label: isShort ? '⑤ SHORT Setup' : '⑤ LONG Setup',
        description: `Entry: ${primarySetup.entry_zone?.[0]?.toFixed(0) || 'N/A'} | Stop: ${primarySetup.stop_loss?.toFixed(0) || 'N/A'}`,
        time: null, // Current time
        price: primarySetup.entry_zone?.[0],
        stopLoss: primarySetup.stop_loss,
        target1: primarySetup.target_1,
        direction: isShort ? 'bearish' : 'bullish',
        priority: 5,
        color: isShort ? '#ef4444' : '#22c55e',
        markerPosition: 'inBar',
        shape: 'square',
        confidence: confidence,
      });
    }
  }
  
  // Sort by priority
  return events.sort((a, b) => a.priority - b.priority);
}

/**
 * Check if narrative has valid chain
 * A valid narrative needs: sweep + (displacement OR choch) + poi
 */
export function hasValidNarrative(events) {
  const hasSweep = events.some(e => e.type === 'liquidity_sweep');
  const hasDisplacement = events.some(e => e.type === 'displacement');
  const hasCHOCH = events.some(e => e.type === 'choch' && e.isValid);
  const hasPOI = events.some(e => e.type === 'poi');
  
  // Need sweep AND (displacement OR valid choch) AND poi
  return hasSweep && (hasDisplacement || hasCHOCH) && hasPOI;
}

/**
 * Get narrative summary as text
 */
export function getNarrativeSummary(events, decision) {
  if (!events.length) return null;
  
  const bias = decision?.bias || 'neutral';
  const labels = events.map(e => e.label.replace(/[①②③④⑤]/g, '').trim());
  
  return {
    direction: bias,
    chain: labels.join(' → '),
    eventCount: events.length,
    hasEntry: events.some(e => e.type === 'entry'),
  };
}

export default { buildNarrative, hasValidNarrative, getNarrativeSummary };
