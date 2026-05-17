/**
 * Pattern Render Adapter
 * ======================
 * 
 * Normalizes pattern-v2 API response for frontend rendering.
 * Frontend doesn't understand pattern logic - only render instructions.
 * 
 * Backend decides → Frontend renders
 */

/**
 * @typedef {Object} RenderPoint
 * @property {number} time - Unix timestamp
 * @property {number} price - Price value
 * @property {string} [label] - Optional label
 */

/**
 * @typedef {Object} RenderLine
 * @property {RenderPoint} from
 * @property {RenderPoint} to
 * @property {string} kind - 'upper' | 'lower' | 'neckline'
 */

/**
 * @typedef {Object} NormalizedPattern
 * @property {string} title
 * @property {string} type
 * @property {string} direction - 'bullish' | 'bearish' | 'neutral'
 * @property {number} confidence
 * @property {string} state - 'CLEAR' | 'WEAK' | 'CONFLICTED' | 'COMPRESSION' | 'NONE'
 * @property {boolean} tradeable
 * @property {string} actionability - 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE'
 * @property {string} renderMode - 'box' | 'polyline' | 'two_lines' | 'hs'
 * @property {Object} draw
 * @property {Object} trigger
 * @property {string} [summary]
 * @property {Object} [regimeContext]
 */

/**
 * Format pattern type for display
 */
function formatPatternTitle(type) {
  if (!type) return 'Pattern';
  
  return type
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Adapt pattern-v2 API response to normalized format
 * 
 * @param {Object} apiResponse - Raw API response
 * @returns {NormalizedPattern|null}
 */
export function adaptPatternV2(apiResponse) {
  if (!apiResponse || !apiResponse.ok) return null;
  
  const dominant = apiResponse.dominant;
  const renderContract = apiResponse.render_contract;
  const triggers = apiResponse.triggers;
  
  if (!dominant) return null;
  
  // Get bias/direction from dominant pattern
  const direction = dominant.bias || 'neutral';
  
  // Get interpretation from regime_binding if available
  const regimeBinding = dominant.regime_binding || {};
  const interpretation = regimeBinding.interpretation || [];
  const summary = interpretation.length > 0 
    ? interpretation.join('. ') 
    : `${formatPatternTitle(dominant.type)} detected`;
  
  return {
    title: formatPatternTitle(dominant.type),
    type: dominant.type,
    direction: direction,
    confidence: Number(dominant.confidence || 0),
    state: apiResponse.confidence_state || 'NONE',
    tradeable: Boolean(apiResponse.tradeable),
    actionability: apiResponse.actionability || 'NONE',
    
    // Render contract from backend
    renderMode: renderContract?.render_mode || null,
    renderContract: renderContract,
    
    // ═══════════════════════════════════════════════════════════════
    // RENDER STACK — Multi-pattern visualization (1 dominant + 2 secondary)
    // ═══════════════════════════════════════════════════════════════
    render_stack: apiResponse.render_stack || [],
    
    // Draw instructions (from render_contract)
    draw: {
      lines: renderContract?.lines || [],
      polyline: renderContract?.polyline || [],
      points: renderContract?.points || [],
      levels: renderContract?.levels || [],
      box: renderContract?.box || null,
      window: renderContract?.window || null,
    },
    
    // Trigger levels
    trigger: {
      up: triggers?.bullish_triggers?.[0]?.level || null,
      upMessage: triggers?.bullish_triggers?.[0]?.message || null,
      down: triggers?.bearish_triggers?.[0]?.level || null,
      downMessage: triggers?.bearish_triggers?.[0]?.message || null,
      invalidation: triggers?.invalidation_triggers?.[0]?.level || null,
      invalidationMessage: triggers?.invalidation_triggers?.[0]?.message || null,
      nearest: triggers?.distance_to_nearest || null,
    },
    
    // Additional context
    summary: summary,
    regimeContext: apiResponse.regime_context || null,
    
    // ═══════════════════════════════════════════════════════════════
    // INTERPRETATION — смысл паттернов
    // ═══════════════════════════════════════════════════════════════
    interpretation: apiResponse.interpretation || null,
    
    // Alternatives for info
    alternatives: (apiResponse.alternatives || []).map(alt => ({
      type: alt.type,
      bias: alt.bias,
      confidence: alt.confidence,
    })),
  };
}

/**
 * Get state color for UI
 */
export function getStateColor(state) {
  switch (state) {
    case 'CLEAR': return { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500/50' };
    case 'WEAK': return { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/50' };
    case 'CONFLICTED': return { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/50' };
    case 'COMPRESSION': return { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/50' };
    default: return { bg: 'bg-neutral-500/20', text: 'text-neutral-400', border: 'border-neutral-500/50' };
  }
}

/**
 * Get direction color for UI
 */
export function getDirectionColor(direction) {
  switch (direction) {
    case 'bullish': return { text: 'text-green-400', icon: '▲' };
    case 'bearish': return { text: 'text-red-400', icon: '▼' };
    default: return { text: 'text-neutral-400', icon: '◆' };
  }
}

export default adaptPatternV2;
