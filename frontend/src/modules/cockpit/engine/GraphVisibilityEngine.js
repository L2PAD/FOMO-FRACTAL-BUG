/**
 * Graph Visibility Engine V3
 * ==========================
 * Brain-driven layer prioritization.
 * 
 * NEW PIPELINE:
 *   ta_context → VisualMappingEngine (backend) → render_plan → THIS ENGINE → Chart
 *
 * RULE: Chart = projection of decision.
 *   - If factor is in top_drivers → it appears on chart (from render_plan)
 *   - This engine applies CAPS + LIMITS + STYLE on top of render_plan
 *   - Mode shifts (Classic TA / Smart Money) adjust weights but render_plan is PRIMARY
 *
 * ГЛАВНОЕ ПРАВИЛО: На графике максимум 5-7 СМЫСЛОВЫХ блоков
 */

// ============================================
// VISUAL STYLE CONSTANTS (z-index, opacity)
// ============================================

export const VISUAL_PRIORITY = {
  trade_setup: { zIndex: 100, opacity: 1.0, strokeWidth: 3 },
  pattern_primary: { zIndex: 90, opacity: 0.9, strokeWidth: 2 },
  fib: { zIndex: 70, opacity: 0.5, strokeWidth: 1 },
  poi: { zIndex: 30, opacity: 0.15, strokeWidth: 0 },
  liquidity: { zIndex: 60, opacity: 0.7, strokeWidth: 1.5 },
  indicators_overlay: { zIndex: 40, opacity: 0.6, strokeWidth: 1 },
  indicators_panes: { zIndex: 20, opacity: 0.8, strokeWidth: 1 },
  choch: { zIndex: 50, opacity: 0.7, strokeWidth: 1.5 },
  displacement: { zIndex: 35, opacity: 0.4, strokeWidth: 1 },
  structure_labels: { zIndex: 25, opacity: 0.5, strokeWidth: 0 },
  sweep_markers: { zIndex: 45, opacity: 0.6, strokeWidth: 1 },
};

export const LAYER_PRIORITY = {
  trade_setup: 100,
  pattern_primary: 90,
  fib: 80,
  poi: 70,
  liquidity: 60,
  indicators_overlay: 50,
  indicators_panes: 40,
  alternative_pattern: 30,
  choch: 25,
  displacement: 20,
  structure_labels: 15,
  sweep_markers: 10,
};

export const VISIBILITY_MODES = {
  auto: 'auto',
  classic_ta: 'classic',
  smart_money: 'smart',
  minimal: 'minimal',
};

// ============================================
// MAX VISIBLE ELEMENTS
// ============================================

const MAX_VISIBLE = {
  total_layers: 7,
  min_layers: 3,
  overlays: 3,
  panes: 2,
  poi_zones: 2,
  liquidity_levels: 3,
  patterns: 1,
  fib_levels: 5,
  choch_labels: 1,
  sweep_markers: 2,
};

// ============================================
// MAIN ENGINE — render_plan DRIVEN
// ============================================

/**
 * Compute visibility from render_plan (brain-driven).
 * 
 * render_plan is the PRIMARY source (what the brain decided matters).
 * Mode (classic/smart/minimal) can override to add/suppress layers.
 * Caps ensure the chart isn't overloaded.
 * 
 * @param {Object} ctx - Chart context (setup, pattern, poi, etc.)
 * @param {string} mode - Visibility mode
 * @param {Object|null} renderPlan - From backend VisualMappingEngine
 * @returns {Object} Visibility decisions for each layer
 */
export function computeVisibility(ctx, mode = 'auto', renderPlan = null) {
  // ══════════════════════════════════════════════
  // If we have a render_plan, use it as PRIMARY source
  // ══════════════════════════════════════════════
  if (renderPlan && mode !== 'manual') {
    return computeFromRenderPlan(ctx, mode, renderPlan);
  }
  
  // ══════════════════════════════════════════════
  // FALLBACK: Legacy mode (no render_plan or manual mode)
  // ══════════════════════════════════════════════
  return computeLegacy(ctx, mode);
}

/**
 * Brain-driven visibility from render_plan.
 * render_plan says: "show EMA, RSI, POI, Fib because THESE influenced the decision"
 */
function computeFromRenderPlan(ctx, mode, renderPlan) {
  // Start with all OFF by default for clarity
  const visible = {
    trade_setup: false,
    pattern_primary: false,
    fib: false,
    poi: false,
    liquidity: false,
    indicators_overlay: false,
    indicators_panes: false,
    alternative_pattern: false,
    choch: false,
    displacement: false,
    structure_labels: false,
    sweep_markers: false,
    levels: true,      // Always show levels (support/resistance)
    structure: true,   // Always show structure by default
    patterns: false,
  };
  
  // ══════════════════════════════════════════════
  // BASE: From render_plan flags
  // ══════════════════════════════════════════════
  if (renderPlan.overlays?.length > 0)   visible.indicators_overlay = true;
  if (renderPlan.panes?.length > 0)      visible.indicators_panes = true;
  if (renderPlan.show_fib)               visible.fib = true;
  if (renderPlan.show_poi)               visible.poi = true;
  if (renderPlan.show_liquidity)         visible.liquidity = true;
  if (renderPlan.show_choch)             visible.choch = true;
  if (renderPlan.show_displacement)      visible.displacement = true;
  
  // Pattern if exists
  if (ctx.pattern_primary?.type) {
    visible.pattern_primary = true;
    visible.patterns = true;
  }
  
  // Trade setup if valid
  const hasValidSetup = ctx.setup?.primary?.valid || ctx.setup?.confidence > 0.7;
  if (hasValidSetup) {
    visible.trade_setup = true;
  }
  
  // ══════════════════════════════════════════════
  // MODE OVERRIDES - Each mode has distinct behavior
  // ══════════════════════════════════════════════
  if (mode === 'auto') {
    // Auto: Show everything that exists in render_plan
    // Already set above from render_plan flags
    visible.structure = true;
    visible.structure_labels = true;
  } else if (mode === 'classic') {
    // Classic TA: Indicators + Patterns + Fibonacci, NO Smart Money
    visible.indicators_overlay = true;
    visible.indicators_panes = true;
    visible.fib = true;
    visible.pattern_primary = ctx.pattern_primary?.type ? true : false;
    visible.patterns = visible.pattern_primary;
    visible.structure = true;
    visible.structure_labels = true;
    // OFF: Smart Money concepts
    visible.choch = false;
    visible.displacement = false;
    visible.sweep_markers = false;
    visible.poi = false;
    visible.liquidity = false;
  } else if (mode === 'smart') {
    // Smart Money: POI, Liquidity, CHOCH, Displacement
    visible.poi = true;
    visible.liquidity = true;
    visible.choch = true;
    visible.displacement = true;
    visible.sweep_markers = true;
    visible.structure = true;
    visible.structure_labels = true;
    // OFF: Traditional TA
    visible.indicators_overlay = false;
    visible.indicators_panes = false;
    visible.fib = false;
  } else if (mode === 'minimal') {
    // Minimal: Only price action + key levels
    visible.structure = true;
    visible.levels = true;
    // OFF: Everything else
    visible.pattern_primary = false;
    visible.patterns = false;
    visible.fib = false;
    visible.poi = false;
    visible.liquidity = false;
    visible.indicators_overlay = false;
    visible.indicators_panes = false;
    visible.choch = false;
    visible.displacement = false;
    visible.sweep_markers = false;
    visible.structure_labels = false;
    visible.trade_setup = false;
  }
  
  return visible;
}

/**
 * Legacy visibility computation (no render_plan)
 */
function computeLegacy(ctx, mode) {
  const {
    setup, pattern_primary, poi, liquidity, fib,
    indicators, choch, displacement, structure_context, current_price,
  } = ctx;

  const priorities = { ...LAYER_PRIORITY };

  // Mode weight shifts
  const MODE_ADJUSTMENTS = {
    classic: {
      indicators_overlay: +20, indicators_panes: +15, fib: +10, pattern_primary: +10,
      poi: -15, liquidity: -20, choch: -25, displacement: -25,
    },
    smart: {
      poi: +20, liquidity: +15, choch: +15, displacement: +10,
      indicators_overlay: -15, indicators_panes: -20, fib: -5,
    },
    minimal: {
      trade_setup: +15, pattern_primary: +10, fib: +5,
      indicators_overlay: -40, indicators_panes: -50, poi: -30, liquidity: -35,
      choch: -50, displacement: -50, sweep_markers: -60, structure_labels: -50,
      alternative_pattern: -40,
    },
  };

  if (mode !== 'auto' && MODE_ADJUSTMENTS[mode]) {
    Object.entries(MODE_ADJUSTMENTS[mode]).forEach(([layer, adj]) => {
      if (priorities[layer] !== undefined) priorities[layer] += adj;
    });
  }

  const hasValidSetup = setup?.primary?.valid || setup?.confidence > 0.7;
  const hasPattern = !!pattern_primary?.type;
  const regime = detectRegime(structure_context);
  const poiNearPrice = isPOINearPrice(poi, current_price);
  const liquidityNearPrice = isLiquidityNearPrice(liquidity, current_price);

  if (hasValidSetup) {
    priorities.trade_setup += 30;
    priorities.poi += 20;
    priorities.pattern_primary += 15;
  }
  if (!hasValidSetup && hasPattern) {
    priorities.pattern_primary += 15;
    priorities.fib += 10;
    priorities.indicators_overlay += 10;
    priorities.indicators_panes += 10;
  }
  if (regime === 'range' || regime === 'compression') {
    priorities.indicators_panes += 20;
    priorities.fib -= 15;
    priorities.displacement -= 30;
  }
  if (regime === 'trend_up' || regime === 'trend_down') {
    priorities.indicators_overlay += 15;
    priorities.fib += 20;
    priorities.indicators_panes -= 15;
  }

  const sortedLayers = Object.entries(priorities).sort(([, a], [, b]) => b - a);
  const visible = {};
  Object.keys(LAYER_PRIORITY).forEach(l => { visible[l] = false; });

  let visibleCount = 0;
  const maxLayers = mode === 'minimal' ? 4 : MAX_VISIBLE.total_layers;

  for (const [layer, priority] of sortedLayers) {
    if (visibleCount >= maxLayers) break;
    if (!checkLayerHasContent(layer, ctx)) continue;
    if (mode !== 'smart') {
      if (layer === 'poi' && !poiNearPrice) continue;
      if (layer === 'liquidity' && !liquidityNearPrice) continue;
    }
    if (priority < 15) continue;
    visible[layer] = true;
    visibleCount++;
  }

  if (hasValidSetup && !visible.trade_setup) visible.trade_setup = true;
  if (hasPattern && !visible.pattern_primary) visible.pattern_primary = true;

  return visible;
}

// ============================================
// HELPERS
// ============================================

const isPOINearPrice = (poi, currentPrice, threshold = 0.05) => {
  if (!poi?.zones?.length || !currentPrice) return false;
  return poi.zones.some(zone => {
    const zoneCenter = (zone.high + zone.low) / 2;
    return Math.abs(zoneCenter - currentPrice) / currentPrice <= threshold;
  });
};

const isLiquidityNearPrice = (liquidity, currentPrice, threshold = 0.04) => {
  if (!liquidity || !currentPrice) return false;
  const all = [...(liquidity.equal_highs || []), ...(liquidity.equal_lows || [])];
  return all.some(lvl => lvl.price && Math.abs(lvl.price - currentPrice) / currentPrice <= threshold);
};

const detectRegime = (structureContext) => {
  if (!structureContext) return 'unknown';
  const regime = structureContext.regime || structureContext.trend || 'unknown';
  if (regime.includes('up') || regime.includes('bullish')) return 'trend_up';
  if (regime.includes('down') || regime.includes('bearish')) return 'trend_down';
  if (regime.includes('range') || regime.includes('consolidation')) return 'range';
  return regime;
};

function checkLayerHasContent(layer, ctx) {
  switch (layer) {
    case 'trade_setup':      return ctx.setup?.primary?.valid || ctx.setup?.confidence > 0.5;
    case 'pattern_primary':  return !!ctx.pattern_primary?.type;
    case 'alternative_pattern': return !!ctx.pattern_alternative?.type;
    case 'poi':              return ctx.poi?.zones?.length > 0;
    case 'liquidity':        return (ctx.liquidity?.equal_highs?.length > 0) || (ctx.liquidity?.equal_lows?.length > 0);
    case 'fib':              return !!ctx.fib?.fib_set;
    case 'indicators_overlay': return ctx.indicators?.overlays?.length > 0;
    case 'indicators_panes': return ctx.indicators?.panes?.length > 0;
    case 'choch':            return !!ctx.choch?.confirmed || !!ctx.choch?.potential;
    case 'displacement':     return ctx.displacement?.detected;
    case 'structure_labels': return ctx.structure_context?.structure?.length > 0;
    case 'sweep_markers':    return ctx.liquidity?.sweeps?.length > 0;
    default:                 return true;
  }
}

// ============================================
// PUBLIC API
// ============================================

export function getLayerLimits(mode = 'auto') {
  const limits = { ...MAX_VISIBLE };
  if (mode === 'minimal') {
    limits.total_layers = 4; limits.overlays = 1; limits.panes = 1;
    limits.poi_zones = 1; limits.liquidity_levels = 2; limits.fib_levels = 3;
  }
  if (mode === 'classic') { limits.overlays = 3; limits.panes = 2; }
  if (mode === 'smart') { limits.overlays = 1; limits.panes = 1; limits.poi_zones = 2; limits.liquidity_levels = 4; }
  return limits;
}

export function applyLimits(elements, type, limits, currentPrice = null) {
  const limit = limits[type];
  if (!limit || !elements || !Array.isArray(elements)) return elements;
  if (currentPrice && elements.length > limit) {
    const sorted = [...elements].sort((a, b) => {
      const pA = a.price || a.value || a.level || 0;
      const pB = b.price || b.value || b.level || 0;
      return Math.abs(pA - currentPrice) - Math.abs(pB - currentPrice);
    });
    return sorted.slice(0, limit);
  }
  return elements.slice(0, limit);
}

export function getLayerStyle(layer) {
  return VISUAL_PRIORITY[layer] || { zIndex: 50, opacity: 0.5, strokeWidth: 1 };
}

export function getLayerOpacity(layer, priorities, visible) {
  if (!visible[layer]) return 0;
  const style = VISUAL_PRIORITY[layer];
  return style?.opacity || 0.5;
}

export function getLayerZIndex(layer) {
  const style = VISUAL_PRIORITY[layer];
  return style?.zIndex || 50;
}

export function getLayerStrokeWidth(layer) {
  const style = VISUAL_PRIORITY[layer];
  return style?.strokeWidth || 1;
}

export default {
  computeVisibility,
  getLayerLimits,
  applyLimits,
  getLayerStyle,
  getLayerOpacity,
  getLayerZIndex,
  getLayerStrokeWidth,
  LAYER_PRIORITY,
  VISIBILITY_MODES,
  VISUAL_PRIORITY,
  MAX_VISIBLE,
};
