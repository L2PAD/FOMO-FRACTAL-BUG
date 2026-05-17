/**
 * Pattern Render Engine v4
 * =========================
 * 
 * Renders patterns as proper TA formations, not pivot connections.
 * 
 * Key principles:
 * 1. Patterns live inside bounded time windows
 * 2. Boundaries are clean trendlines, not extrapolated
 * 3. Frontend draws primitives directly from render contract
 * 4. No geometry reconstruction
 * 
 * Usage:
 *   import { renderPattern, clearPattern } from './patternRenderer';
 *   const objects = renderPattern(chart, candleSeries, patternContract);
 *   // Later: clearPattern(objects);
 */

import { LineSeries } from 'lightweight-charts';

// ═══════════════════════════════════════════════════════════════
// BOUNDARY RENDERER
// ═══════════════════════════════════════════════════════════════

/**
 * Draw pattern boundaries (trendlines)
 * 
 * CRITICAL:
 * - Lines ONLY between x1 and x2
 * - NO extrapolation
 * - Clean styling
 */
export function drawBoundaries(chart, boundaries, options = {}) {
  if (!chart || !boundaries?.length) return [];
  
  const lines = [];
  const { 
    primaryColor = '#3B82F6',  // Blue
    secondaryColor = '#9CA3AF',
    lineWidth = 3,
    boundaryWidth = 3,
  } = options;
  
  const actualWidth = boundaryWidth || lineWidth;
  
  console.log('[PatternRenderer] drawBoundaries:', boundaries.length, 'boundaries');
  
  boundaries.forEach(boundary => {
    if (!boundary || boundary.kind !== 'trendline') return;
    
    const { x1, y1, x2, y2, style = 'primary' } = boundary;
    
    if (x1 == null || y1 == null || x2 == null || y2 == null) {
      console.warn('[PatternRenderer] Missing coordinates:', boundary);
      return;
    }
    
    try {
      const line = chart.addSeries(LineSeries, {
        color: primaryColor,
        lineWidth: actualWidth,
        lineStyle: 0,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      
      line.setData([
        { time: x1, value: y1 },
        { time: x2, value: y2 },
      ]);
      
      console.log(`[PatternRenderer] ${boundary.id} rendered`);
      lines.push(line);
    } catch (e) {
      console.warn('[PatternRenderer] FAILED:', e);
    }
  });
  
  return lines;
}


// ═══════════════════════════════════════════════════════════════
// LEVEL RENDERER (neckline, breakout, support/resistance)
// ═══════════════════════════════════════════════════════════════

/**
 * Draw horizontal levels
 */
export function drawLevels(chart, levels, options = {}) {
  if (!chart || !levels?.length) return [];
  
  const {
    necklineColor = '#EF4444',    // Red
    breakoutColor = '#10B981',    // Green
    defaultColor = '#9CA3AF',     // Gray
    lineWidth = 1,
  } = options;
  
  const lines = [];
  
  levels.forEach(level => {
    if (!level || level.price == null) return;
    
    const { price, kind, start, end, label } = level;
    
    // Choose color based on level type
    let color = defaultColor;
    if (kind === 'neckline') color = necklineColor;
    if (kind === 'breakout' || kind?.includes('breakout')) color = breakoutColor;
    
    try {
      // Lightweight Charts API
      const line = chart.addSeries(LineSeries, {
        color,
        lineWidth,
        lineStyle: 2, // Dashed
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      
      // Use start/end if provided, otherwise span visible range
      const timeStart = start || 0;
      const timeEnd = end || Math.floor(Date.now() / 1000);
      
      line.setData([
        { time: timeStart, value: price },
        { time: timeEnd, value: price },
      ]);
      
      lines.push(line);
    } catch (e) {
      console.warn('[PatternRenderer] Failed to draw level:', e);
    }
  });
  
  return lines;
}


// ═══════════════════════════════════════════════════════════════
// MARKER RENDERER (LS, H, RS, Top, Bottom markers)
// ═══════════════════════════════════════════════════════════════

/**
 * Draw markers on candle series
 */
export function drawMarkers(candleSeries, markers, options = {}) {
  if (!candleSeries || !markers?.length) return;
  
  const {
    markerColor = '#F59E0B', // Amber
  } = options;
  
  const formatted = markers
    .filter(m => m.time && m.price)
    .map(m => ({
      time: m.time,
      position: m.type === 'trough' ? 'belowBar' : 'aboveBar',
      color: markerColor,
      shape: 'circle',
      text: m.label || '',
    }));
  
  try {
    candleSeries.setMarkers(formatted);
  } catch (e) {
    console.warn('[PatternRenderer] Failed to draw markers:', e);
  }
}


// ═══════════════════════════════════════════════════════════════
// ZONE RENDERER (channel zones, pattern areas)
// ═══════════════════════════════════════════════════════════════

/**
 * Draw filled zones (for channels, etc.)
 * 
 * Note: TradingView Lightweight Charts has limited area support.
 * This creates a simple visual indication using horizontal areas.
 */
export function drawZones(chart, zones, options = {}) {
  if (!chart || !zones?.length) return [];
  
  const {
    zoneColor = 'rgba(59, 130, 246, 0.1)', // Light blue
  } = options;
  
  const areas = [];
  
  // Note: Lightweight Charts doesn't support true rectangular zones.
  // We'll approximate with area series or skip for now.
  // For proper zones, consider using canvas overlay.
  
  return areas;
}


// ═══════════════════════════════════════════════════════════════
// TOUCH POINTS RENDERER (optional - shows where price touched boundaries)
// ═══════════════════════════════════════════════════════════════

/**
 * Draw small markers at touch points
 */
export function drawTouchPoints(candleSeries, touchPoints, options = {}) {
  if (!candleSeries || !touchPoints?.length) return;
  
  const {
    upperColor = '#3B82F6', // Blue
    lowerColor = '#10B981', // Green
  } = options;
  
  const formatted = touchPoints
    .filter(tp => tp.time && tp.price)
    .map(tp => ({
      time: tp.time,
      position: tp.side === 'upper' ? 'aboveBar' : 'belowBar',
      color: tp.side === 'upper' ? upperColor : lowerColor,
      shape: 'square',
      size: 0.5,
    }));
  
  // Note: This would override existing markers
  // Consider using separate series for touch points if needed
}


// ═══════════════════════════════════════════════════════════════
// MAIN PATTERN RENDERER
// ═══════════════════════════════════════════════════════════════

/**
 * Render complete pattern from render contract
 * 
 * @param {Object} chart - TradingView chart instance
 * @param {Object} candleSeries - Main candle series
 * @param {Object} pattern - Pattern render contract from backend
 * @param {Object} options - Rendering options
 * @returns {Object} - Collection of rendered objects for cleanup
 */
export function renderPattern(chart, candleSeries, pattern, options = {}) {
  // PATCH 3: Support both render.boundaries AND top-level boundaries
  if (!chart || !pattern) {
    return { boundaries: [], levels: [], zones: [] };
  }
  
  // Get data from render OR top-level (fallback chain)
  const render = pattern.render || {};
  const boundaries = render.boundaries || pattern.boundaries || [];
  const levels = render.levels || pattern.levels || [];
  const markers = render.markers || pattern.markers || [];
  const zones = render.zones || pattern.zones || [];
  const touch_points = render.touch_points || pattern.touch_points || [];
  const anchors = render.anchors || pattern.anchors || [];
  
  console.log('[PatternRenderer] Data sources:', {
    hasRender: !!pattern.render,
    boundariesCount: boundaries.length,
    levelsCount: levels.length,
    anchorsCount: anchors.length,
  });
  
  const objects = {
    boundaries: [],
    levels: [],
    zones: [],
  };
  
  // Draw boundaries (trendlines)
  if (boundaries?.length) {
    objects.boundaries = drawBoundaries(chart, boundaries, {
      primaryColor: options.boundaryColor || '#3B82F6',
      lineWidth: options.boundaryWidth || 2,
    });
  }
  
  // Draw levels (neckline, breakout)
  if (levels?.length) {
    objects.levels = drawLevels(chart, levels, {
      necklineColor: options.necklineColor || '#EF4444',
      breakoutColor: options.breakoutColor || '#10B981',
    });
  }
  
  // Draw anchor points (shows WHY lines exist)
  if (anchors?.length && candleSeries) {
    drawAnchorPoints(candleSeries, anchors, {
      upperColor: options.upperAnchorColor || '#EF4444',
      lowerColor: options.lowerAnchorColor || '#10B981',
      reactionGlow: options.reactionColor || '#FBBF24',
    });
  }
  // Fallback to markers
  else if (markers?.length && candleSeries) {
    drawMarkers(candleSeries, markers, {
      markerColor: options.markerColor || '#F59E0B',
    });
  }
  
  // Draw zones (if supported)
  if (zones?.length) {
    objects.zones = drawZones(chart, zones);
  }
  
  console.log(`[PatternRenderer] Rendered ${pattern.type}: ` +
    `${objects.boundaries.length} boundaries, ${objects.levels.length} levels, ` +
    `${anchors?.length || 0} anchors`);
  
  return objects;
}


// ═══════════════════════════════════════════════════════════════
// ANCHOR POINTS RENDERER
// ═══════════════════════════════════════════════════════════════

/**
 * Draw anchor points (where lines touch price)
 * 
 * Shows traders WHY the lines exist
 */
export function drawAnchorPoints(candleSeries, anchors, options = {}) {
  if (!candleSeries || !anchors?.length) return;
  
  const {
    upperColor = '#EF4444',   // Red for upper
    lowerColor = '#10B981',   // Green for lower
    reactionGlow = '#FBBF24', // Yellow glow for reactions
  } = options;
  
  const markers = anchors.map(anchor => {
    const isUpper = anchor.type === 'upper';
    const hasReaction = anchor.reaction;
    
    return {
      time: anchor.time,
      position: isUpper ? 'aboveBar' : 'belowBar',
      color: hasReaction ? reactionGlow : (isUpper ? upperColor : lowerColor),
      shape: hasReaction ? 'circle' : 'circle',
      size: hasReaction ? 2 : 1,  // Reactions are bigger
      text: '',  // No text clutter
    };
  });
  
  try {
    candleSeries.setMarkers(markers);
    console.log(`[PatternRenderer] Drew ${markers.length} anchor points`);
  } catch (e) {
    console.warn('[PatternRenderer] Error drawing anchors:', e);
  }
}


// ═══════════════════════════════════════════════════════════════
// CLEANUP
// ═══════════════════════════════════════════════════════════════

/**
 * Clear rendered pattern objects
 * 
 * @param {Object} chart - TradingView chart instance
 * @param {Object} objects - Objects returned from renderPattern
 */
export function clearPattern(chart, objects) {
  if (!chart || !objects) return;
  
  try {
    // Remove boundary lines
    objects.boundaries?.forEach(line => {
      try {
        chart.removeSeries(line);
      } catch (e) {}
    });
    
    // Remove level lines
    objects.levels?.forEach(line => {
      try {
        chart.removeSeries(line);
      } catch (e) {}
    });
    
    // Remove zones
    objects.zones?.forEach(zone => {
      try {
        chart.removeSeries(zone);
      } catch (e) {}
    });
  } catch (e) {
    console.warn('[PatternRenderer] Error clearing pattern:', e);
  }
}


// ═══════════════════════════════════════════════════════════════
// PATTERN INFO COMPONENT
// ═══════════════════════════════════════════════════════════════

/**
 * Get pattern display info
 */
export function getPatternInfo(pattern) {
  if (!pattern) return null;
  
  return {
    label: pattern.label || pattern.type?.replace(/_/g, ' ') || 'Unknown',
    direction: pattern.direction || 'neutral',
    confidence: pattern.confidence || 0,
    renderQuality: pattern.render_quality || 0,
    status: pattern.status || 'active',
  };
}


export default {
  renderPattern,
  clearPattern,
  drawBoundaries,
  drawLevels,
  drawMarkers,
  drawZones,
  getPatternInfo,
};
