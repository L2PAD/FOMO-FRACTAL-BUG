/**
 * Chart Object Renderer
 * ======================
 * 
 * Renders chart objects from unified API response.
 * 
 * RULES:
 * 1. Render ONLY from objects[]
 * 2. Use object.type to determine rendering method
 * 3. Use object.priority for z-order
 * 4. Respect object.visible flag
 * 5. FAIL-SAFE: Don't render invalid objects
 */

import { LineSeries } from 'lightweight-charts';
import { ObjectType, ObjectCategory } from '../utils/chartObjects';

/**
 * Main render function - renders all objects on chart
 */
export function renderChartObjects(chart, objects, options = {}) {
  const renderedSeries = [];
  
  // Sort by priority (lower first = rendered below)
  const sortedObjects = [...objects].sort((a, b) => a.priority - b.priority);
  
  for (const obj of sortedObjects) {
    // Skip invisible objects
    if (!obj.visible) continue;
    
    // Skip objects without valid data
    if (!obj.data) continue;
    
    try {
      const series = renderObject(chart, obj, options);
      if (series) {
        renderedSeries.push(...(Array.isArray(series) ? series : [series]));
      }
    } catch (e) {
      console.warn(`[ObjectRenderer] Failed to render ${obj.type}:`, e.message);
    }
  }
  
  return renderedSeries;
}

/**
 * Render single object based on type
 */
function renderObject(chart, obj, options) {
  switch (obj.type) {
    // PATTERNS
    case ObjectType.CHANNEL:
    case ObjectType.TRIANGLE:
    case ObjectType.WEDGE:
      return renderPatternLines(chart, obj);
    
    case ObjectType.RANGE_BOX:
      return renderRangeBox(chart, obj);
    
    // LEVELS
    case ObjectType.HORIZONTAL_LEVEL:
    case ObjectType.SUPPORT_CLUSTER:
    case ObjectType.RESISTANCE_CLUSTER:
      return renderHorizontalLevel(chart, obj);
    
    case ObjectType.FIBONACCI:
      return renderFibonacci(chart, obj);
    
    // STRUCTURE
    case ObjectType.STRUCTURE_POINT:
      return renderStructureMarker(chart, obj, options);
    
    // HYPOTHESIS
    case ObjectType.HYPOTHESIS_PATH:
      return renderHypothesisPath(chart, obj);
    
    case ObjectType.CONFIDENCE_CORRIDOR:
      return renderConfidenceCorridor(chart, obj);
    
    // TRADING
    case ObjectType.ENTRY_ZONE:
    case ObjectType.STOP_LOSS:
    case ObjectType.TAKE_PROFIT:
    case ObjectType.INVALIDATION_LINE:
      return renderTradingLine(chart, obj);
    
    // INDICATORS
    case ObjectType.EMA_SERIES:
    case ObjectType.SMA_SERIES:
      return renderIndicatorSeries(chart, obj);
    
    case ObjectType.BOLLINGER_BAND:
      return renderBollingerBand(chart, obj);
    
    default:
      console.warn(`[ObjectRenderer] Unknown type: ${obj.type}`);
      return null;
  }
}

/**
 * PATTERN LINES (Channel, Triangle, Wedge)
 * Renders upper and lower trendlines
 */
function renderPatternLines(chart, obj) {
  const { upper, lower } = obj.data;
  const series = [];
  
  // Validate data
  if (!upper || !lower || upper.length < 2 || lower.length < 2) {
    console.warn(`[ObjectRenderer] Invalid pattern data for ${obj.type}`);
    return null;
  }
  
  const color = obj.style?.color || '#3B82F6';
  const lineWidth = obj.style?.width || 2;
  const opacity = obj.style?.opacity || 0.9;
  
  // Upper line
  const upperSeries = chart.addSeries(LineSeries, {
    color: color,
    lineWidth: lineWidth,
    lineStyle: obj.style?.dashed ? 2 : 0,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  });
  
  upperSeries.setData(upper.map(p => ({
    time: p.time,
    value: p.value,
  })));
  
  series.push(upperSeries);
  
  // Lower line
  const lowerSeries = chart.addSeries(LineSeries, {
    color: color,
    lineWidth: lineWidth,
    lineStyle: obj.style?.dashed ? 2 : 0,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  });
  
  lowerSeries.setData(lower.map(p => ({
    time: p.time,
    value: p.value,
  })));
  
  series.push(lowerSeries);
  
  return series;
}

/**
 * HORIZONTAL LEVEL (Support/Resistance)
 */
function renderHorizontalLevel(chart, obj) {
  const { price, points } = obj.data;
  
  if (!price && (!points || points.length < 2)) {
    return null;
  }
  
  const color = obj.style?.color || '#64748b';
  
  const series = chart.addSeries(LineSeries, {
    color: color,
    lineWidth: obj.style?.width || 1,
    lineStyle: obj.style?.dashed ? 2 : 0,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  });
  
  if (points && points.length >= 2) {
    series.setData(points.map(p => ({
      time: p.time,
      value: p.value,
    })));
  } else if (price) {
    // Create line across visible range using price
    // This is a fallback - ideally points should be provided
    console.warn('[ObjectRenderer] Level missing points, using price only');
  }
  
  return series;
}

/**
 * RANGE BOX
 */
function renderRangeBox(chart, obj) {
  const { upper, lower } = obj.data;
  
  if (!upper || !lower) return null;
  
  const series = [];
  const color = obj.style?.color || '#8B5CF6';
  
  // Upper boundary
  const upperSeries = chart.addSeries(LineSeries, {
    color: color,
    lineWidth: 1,
    lineStyle: 2,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  upperSeries.setData(upper.map(p => ({ time: p.time, value: p.value })));
  series.push(upperSeries);
  
  // Lower boundary
  const lowerSeries = chart.addSeries(LineSeries, {
    color: color,
    lineWidth: 1,
    lineStyle: 2,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  lowerSeries.setData(lower.map(p => ({ time: p.time, value: p.value })));
  series.push(lowerSeries);
  
  return series;
}

/**
 * FIBONACCI LEVELS
 */
function renderFibonacci(chart, obj) {
  const { levels } = obj.data;
  
  if (!levels || !Array.isArray(levels)) return null;
  
  const series = [];
  
  levels.forEach((level, i) => {
    const levelSeries = chart.addSeries(LineSeries, {
      color: obj.style?.color || '#F59E0B',
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    
    if (level.points) {
      levelSeries.setData(level.points.map(p => ({
        time: p.time,
        value: p.value,
      })));
    }
    
    series.push(levelSeries);
  });
  
  return series;
}

/**
 * STRUCTURE MARKER (HH, HL, LH, LL, BOS, CHOCH)
 */
function renderStructureMarker(chart, obj, options) {
  const { point, marker_type } = obj.data;
  
  if (!point) return null;
  
  // Structure markers are rendered as markers on the candlestick series
  // We need access to the main series - this requires different approach
  // For now, we'll create a small point series
  
  const color = obj.style?.color || '#64748b';
  
  const series = chart.addSeries(LineSeries, {
    color: color,
    lineWidth: 0,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: true,
    crosshairMarkerRadius: 4,
  });
  
  // Single point
  series.setData([{
    time: point.time,
    value: point.value,
  }]);
  
  // Add marker
  series.setMarkers([{
    time: point.time,
    position: marker_type.includes('H') ? 'aboveBar' : 'belowBar',
    color: color,
    shape: marker_type.includes('H') ? 'arrowDown' : 'arrowUp',
    text: marker_type,
  }]);
  
  return series;
}

/**
 * HYPOTHESIS PATH (Projection)
 */
function renderHypothesisPath(chart, obj) {
  const { points } = obj.data;
  
  if (!points || points.length < 2) return null;
  
  const color = obj.style?.color || '#A78BFA';
  
  const series = chart.addSeries(LineSeries, {
    color: color,
    lineWidth: obj.style?.width || 2,
    lineStyle: 2, // Dashed
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  });
  
  series.setData(points.map(p => ({
    time: p.time,
    value: p.value,
  })));
  
  return series;
}

/**
 * CONFIDENCE CORRIDOR
 */
function renderConfidenceCorridor(chart, obj) {
  const { upper, lower } = obj.data;
  
  if (!upper || !lower) return null;
  
  const series = [];
  const color = obj.style?.color || '#64748b';
  const opacity = obj.style?.opacity || 0.3;
  
  // Upper boundary
  const upperSeries = chart.addSeries(LineSeries, {
    color: color,
    lineWidth: 1,
    lineStyle: 1,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  });
  upperSeries.setData(upper.map(p => ({ time: p.time, value: p.value })));
  series.push(upperSeries);
  
  // Lower boundary
  const lowerSeries = chart.addSeries(LineSeries, {
    color: color,
    lineWidth: 1,
    lineStyle: 1,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  });
  lowerSeries.setData(lower.map(p => ({ time: p.time, value: p.value })));
  series.push(lowerSeries);
  
  return series;
}

/**
 * TRADING LINE (Entry, Stop, Take Profit, Invalidation)
 */
function renderTradingLine(chart, obj) {
  const { price, point, zone } = obj.data;
  
  const actualPrice = price || point?.value;
  if (!actualPrice) return null;
  
  const color = obj.style?.color || '#3B82F6';
  
  // For zones with range (Entry Zone)
  if (zone && zone.length === 2) {
    const series = [];
    
    // Upper zone line
    const upperSeries = chart.addSeries(LineSeries, {
      color: color,
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    
    // Lower zone line
    const lowerSeries = chart.addSeries(LineSeries, {
      color: color,
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    
    // Need time range - use point if available
    if (point) {
      const startTime = point.time;
      const endTime = point.time + 86400 * 5; // 5 days ahead
      
      upperSeries.setData([
        { time: startTime, value: zone[1] },
        { time: endTime, value: zone[1] },
      ]);
      
      lowerSeries.setData([
        { time: startTime, value: zone[0] },
        { time: endTime, value: zone[0] },
      ]);
    }
    
    series.push(upperSeries, lowerSeries);
    return series;
  }
  
  // Single line (SL, TP, Invalidation)
  const series = chart.addSeries(LineSeries, {
    color: color,
    lineWidth: obj.style?.width || 1,
    lineStyle: obj.style?.dashed ? 2 : 0,
    priceLineVisible: false,
    lastValueVisible: true,
    crosshairMarkerVisible: false,
  });
  
  if (point) {
    const startTime = point.time;
    const endTime = point.time + 86400 * 10; // 10 days ahead
    
    series.setData([
      { time: startTime, value: actualPrice },
      { time: endTime, value: actualPrice },
    ]);
  }
  
  return series;
}

/**
 * INDICATOR SERIES (EMA, SMA)
 */
function renderIndicatorSeries(chart, obj) {
  const { values } = obj.data;
  
  if (!values || values.length < 2) return null;
  
  const color = obj.style?.color || '#F59E0B';
  
  const series = chart.addSeries(LineSeries, {
    color: color,
    lineWidth: obj.style?.width || 1,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  });
  
  series.setData(values.map(p => ({
    time: p.time,
    value: p.value,
  })));
  
  return series;
}

/**
 * BOLLINGER BAND
 */
function renderBollingerBand(chart, obj) {
  const { upper, middle, lower } = obj.data;
  
  if (!upper || !middle || !lower) return null;
  
  const series = [];
  const color = obj.style?.color || '#06B6D4';
  
  // Upper band
  const upperSeries = chart.addSeries(LineSeries, {
    color: color,
    lineWidth: 1,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  upperSeries.setData(upper.map(p => ({ time: p.time, value: p.value })));
  series.push(upperSeries);
  
  // Middle band
  const middleSeries = chart.addSeries(LineSeries, {
    color: color,
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  middleSeries.setData(middle.map(p => ({ time: p.time, value: p.value })));
  series.push(middleSeries);
  
  // Lower band
  const lowerSeries = chart.addSeries(LineSeries, {
    color: color,
    lineWidth: 1,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  lowerSeries.setData(lower.map(p => ({ time: p.time, value: p.value })));
  series.push(lowerSeries);
  
  return series;
}

/**
 * Clear all rendered objects from chart
 */
export function clearChartObjects(chart, series) {
  if (!series || !Array.isArray(series)) return;
  
  for (const s of series) {
    try {
      chart.removeSeries(s);
    } catch (e) {
      // Series might already be removed
    }
  }
}

export default {
  renderChartObjects,
  clearChartObjects,
};
