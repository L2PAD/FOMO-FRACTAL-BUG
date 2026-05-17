/**
 * PatternGeometryRenderer
 * ========================
 * Renders pattern geometry DIRECTLY ON PRICE, not in a panel.
 * 
 * Patterns drawn:
 * - Double Bottom: 2 low points + neckline
 * - Double Top: 2 high points + neckline  
 * - Triangle: upper + lower trendlines
 * - Channel: parallel lines
 * - Head & Shoulders: 3 peaks + neckline
 * - Wedge: converging trendlines
 * 
 * Priority: HIGHEST (above structure, indicators)
 */

import { LineSeries } from 'lightweight-charts';

// Pattern colors — prominent, distinguishable
const PATTERN_COLORS = {
  // Double patterns
  doubleLows: '#fbbf24',        // Amber for double bottom points
  doubleHighs: '#f97316',       // Orange for double top points
  neckline: '#8b5cf6',          // Purple for neckline
  
  // Triangles & wedges
  upperTrendline: '#ef4444',    // Red for resistance trendline
  lowerTrendline: '#22c55e',    // Green for support trendline
  
  // Channels
  channelUpper: '#f472b6',      // Pink upper
  channelLower: '#a78bfa',      // Violet lower
  
  // Breakout/Invalidation zones
  breakoutZone: 'rgba(34, 197, 94, 0.15)',
  invalidationZone: 'rgba(239, 68, 68, 0.15)',
  
  // EXECUTION LEVELS (NEW!)
  entryZone: 'rgba(59, 130, 246, 0.25)',  // Blue translucent for entry
  entryLine: '#3b82f6',                    // Blue for entry line
  stopLoss: '#ef4444',                     // Red for stop loss
  takeProfit1: '#22c55e',                  // Green for TP1
  takeProfit2: '#10b981',                  // Emerald for TP2
  
  // Pattern fill (subtle)
  patternFill: 'rgba(139, 92, 246, 0.08)', // Very light purple fill
};

/**
 * Derive execution levels from pattern geometry
 * @param {Object} pattern - Pattern data
 * @param {String} direction - 'bullish' or 'bearish'
 * @returns {Object} Execution levels
 */
function derivePatternExecution(pattern, direction) {
  const breakout = pattern.breakout_level;
  const invalidation = pattern.invalidation;
  
  if (!breakout || !invalidation) return null;
  
  const height = Math.abs(breakout - invalidation);
  
  if (direction === 'bullish' || pattern.direction_bias === 'bullish') {
    return {
      entry_zone: [breakout, breakout * 1.005],
      stop: invalidation * 0.995,
      tp1: breakout + height,
      tp2: breakout + height * 1.618,
    };
  } else {
    return {
      entry_zone: [breakout * 0.995, breakout],
      stop: invalidation * 1.005,
      tp1: breakout - height,
      tp2: breakout - height * 1.618,
    };
  }
}

/**
 * Render pattern geometry on chart
 * @param {Object} chart - Lightweight Charts instance
 * @param {Object} patternV2 - Pattern data from API (pattern_v2)
 * @param {Array} candles - Candle data for time reference
 */
export function renderPatternGeometry(chart, patternV2, candles) {
  if (!chart || !patternV2?.primary_pattern) return [];
  
  const pattern = patternV2.primary_pattern;
  const seriesList = [];
  
  const patternType = (pattern.type || '').toLowerCase();
  
  // Get time boundaries
  const startIdx = pattern.start_index || 0;
  const endIdx = pattern.end_index || candles.length - 1;
  const startTime = candles[Math.max(0, startIdx)]?.time;
  const endTime = candles[Math.min(candles.length - 1, endIdx)]?.time;
  const lastTime = candles[candles.length - 1]?.time;
  
  // Normalize time
  const normalizeTime = (t) => t > 1e12 ? Math.floor(t / 1000) : t;
  
  // Deduplicate points by time - adds small offset for duplicates instead of removing
  const dedupeByTime = (points) => {
    if (!points?.length) return [];
    
    // Sort by time first
    const sorted = [...points].sort((a, b) => a.time - b.time);
    
    const result = [];
    const seenTimes = new Map();
    
    for (const p of sorted) {
      let time = p.time;
      
      // If we've seen this time before, add a small offset (1 second)
      if (seenTimes.has(time)) {
        const count = seenTimes.get(time);
        time = time + count; // Add seconds to make unique
        seenTimes.set(p.time, count + 1);
      } else {
        seenTimes.set(time, 1);
      }
      
      result.push({ time, value: p.value });
    }
    
    return result;
  };
  
  // ========================================
  // UNIVERSAL POINTS FORMAT HANDLER
  // Handles both pattern.lines[] and pattern.points.points[] formats
  // ========================================
  const rawPoints = pattern.points?.points || [];
  if (rawPoints.length >= 2 && !pattern.lines?.length) {
    // Extract upper/lower lines from points array
    const highPoints = rawPoints
      .filter(p => p.type?.includes('high'))
      .map(p => ({ time: normalizeTime(p.time), value: p.price }));
    const lowPoints = rawPoints
      .filter(p => p.type?.includes('low'))
      .map(p => ({ time: normalizeTime(p.time), value: p.price }));
    
    // Render upper line (resistance) - THICK 3-4px
    if (highPoints.length >= 2) {
      const upperSeries = chart.addSeries(LineSeries, {
        color: PATTERN_COLORS.upperTrendline,
        lineWidth: 3,  // Thick for visual prominence
        lineStyle: 0,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      upperSeries.setData(dedupeByTime(highPoints));
      seriesList.push(upperSeries);
    }
    
    // Render lower line (support) - THICK 3-4px
    if (lowPoints.length >= 2) {
      const lowerSeries = chart.addSeries(LineSeries, {
        color: PATTERN_COLORS.lowerTrendline,
        lineWidth: 3,  // Thick for visual prominence
        lineStyle: 0,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      lowerSeries.setData(dedupeByTime(lowPoints));
      seriesList.push(lowerSeries);
    }
    
    // If we rendered from points, add breakout/invalidation and return
    if (seriesList.length > 0) {
      // Breakout level
      if (pattern.breakout_level) {
        const breakoutSeries = chart.addSeries(LineSeries, {
          color: '#22c55e',
          lineWidth: 2,
          lineStyle: 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        const ptTime = highPoints[0]?.time || lowPoints[0]?.time || normalizeTime(startTime);
        breakoutSeries.setData([
          { time: ptTime, value: pattern.breakout_level },
          { time: normalizeTime(lastTime), value: pattern.breakout_level },
        ]);
        seriesList.push(breakoutSeries);
      }
      
      // Invalidation level
      if (pattern.invalidation) {
        const invalSeries = chart.addSeries(LineSeries, {
          color: '#ef4444',
          lineWidth: 2,
          lineStyle: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        const ptTime = highPoints[0]?.time || lowPoints[0]?.time || normalizeTime(startTime);
        invalSeries.setData([
          { time: ptTime, value: pattern.invalidation },
          { time: normalizeTime(lastTime), value: pattern.invalidation },
        ]);
        seriesList.push(invalSeries);
      }
      
      return seriesList;
    }
  }
  
  try {
    // ========================================
    // DOUBLE BOTTOM
    // ========================================
    if (patternType.includes('double_bottom')) {
      // Get valleys from lines array
      const valleyLine = pattern.lines?.find(l => l.name === 'valleys');
      const necklineLine = pattern.lines?.find(l => l.name === 'neckline');
      const neckline = pattern.breakout_level || necklineLine?.points?.[0]?.value;
      
      if (valleyLine?.points?.length >= 2) {
        // Draw line connecting the two valleys (lows) — THICK for emphasis
        const lowSeries = chart.addSeries(LineSeries, {
          color: PATTERN_COLORS.doubleLows,
          lineWidth: 4,  // Thicker for visual hierarchy
          lineStyle: 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        
        const lowPoints = dedupeByTime(valleyLine.points.map(pt => ({
          time: normalizeTime(pt.time),
          value: pt.value,
        })));
        
        lowSeries.setData(lowPoints);
        seriesList.push(lowSeries);
      }
      
      // Draw neckline (horizontal, extends to current) — PROMINENT
      if (neckline) {
        const neckSeries = chart.addSeries(LineSeries, {
          color: PATTERN_COLORS.neckline,
          lineWidth: 3,  // Thicker neckline
          lineStyle: 0,  // Solid, not dashed — more emphasis
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        neckSeries.setData([
          { time: normalizeTime(startTime), value: neckline },
          { time: normalizeTime(lastTime), value: neckline },
        ]);
        seriesList.push(neckSeries);
      }
    }
    
    // ========================================
    // DOUBLE TOP
    // ========================================
    else if (patternType.includes('double_top')) {
      const peakLine = pattern.lines?.find(l => l.name === 'peaks');
      const necklineLine = pattern.lines?.find(l => l.name === 'neckline');
      const neckline = pattern.breakout_level || necklineLine?.points?.[0]?.value;
      
      if (peakLine?.points?.length >= 2) {
        const highSeries = chart.addSeries(LineSeries, {
          color: PATTERN_COLORS.doubleHighs,
          lineWidth: 3,
          lineStyle: 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        
        const highPoints = dedupeByTime(peakLine.points.map(pt => ({
          time: normalizeTime(pt.time),
          value: pt.value,
        })));
        
        highSeries.setData(highPoints);
        seriesList.push(highSeries);
      }
      
      if (neckline) {
        const neckSeries = chart.addSeries(LineSeries, {
          color: PATTERN_COLORS.neckline,
          lineWidth: 2,
          lineStyle: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        neckSeries.setData([
          { time: normalizeTime(startTime), value: neckline },
          { time: normalizeTime(lastTime), value: neckline },
        ]);
        seriesList.push(neckSeries);
      }
    }
    
    // ========================================
    // TRIANGLE (Ascending, Descending, Symmetrical)
    // PRIMARY VISUAL ELEMENT — 3-4px lines per spec
    // ========================================
    else if (patternType.includes('triangle')) {
      const upperLine = pattern.lines?.find(l => l.name === 'upper' || l.name === 'resistance');
      const lowerLine = pattern.lines?.find(l => l.name === 'lower' || l.name === 'support');
      
      // Upper trendline - THICK (3-4px) - PRIMARY VISUAL
      if (upperLine?.points?.length >= 2) {
        const upperSeries = chart.addSeries(LineSeries, {
          color: PATTERN_COLORS.upperTrendline,
          lineWidth: 3,  // Increased to 3px per spec
          lineStyle: 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        const pts = dedupeByTime(upperLine.points.map(p => ({
          time: normalizeTime(p.time),
          value: p.value,
        })));
        upperSeries.setData(pts);
        seriesList.push(upperSeries);
      }
      
      // Lower trendline - THICK (3-4px) - PRIMARY VISUAL
      if (lowerLine?.points?.length >= 2) {
        const lowerSeries = chart.addSeries(LineSeries, {
          color: PATTERN_COLORS.lowerTrendline,
          lineWidth: 3,  // Increased to 3px per spec
          lineStyle: 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        const pts = dedupeByTime(lowerLine.points.map(p => ({
          time: normalizeTime(p.time),
          value: p.value,
        })));
        lowerSeries.setData(pts);
        seriesList.push(lowerSeries);
      }
    }
    
    // ========================================
    // CHANNEL (Ascending, Descending)
    // PRIMARY VISUAL ELEMENT — 3px lines per spec
    // ========================================
    else if (patternType.includes('channel')) {
      const upperChannel = pattern.lines?.find(l => l.name === 'upper');
      const lowerChannel = pattern.lines?.find(l => l.name === 'lower');
      
      if (upperChannel?.points?.length >= 2) {
        const upperSeries = chart.addSeries(LineSeries, {
          color: PATTERN_COLORS.channelUpper,
          lineWidth: 3,  // Increased to 3px per spec
          lineStyle: 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        upperSeries.setData(dedupeByTime(upperChannel.points.map(p => ({
          time: normalizeTime(p.time),
          value: p.value,
        }))));
        seriesList.push(upperSeries);
      }
      
      if (lowerChannel?.points?.length >= 2) {
        const lowerSeries = chart.addSeries(LineSeries, {
          color: PATTERN_COLORS.channelLower,
          lineWidth: 3,  // Increased to 3px per spec
          lineStyle: 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        lowerSeries.setData(dedupeByTime(lowerChannel.points.map(p => ({
          time: normalizeTime(p.time),
          value: p.value,
        }))));
        seriesList.push(lowerSeries);
      }
    }
    
    // ========================================
    // HEAD & SHOULDERS
    // PRIMARY VISUAL ELEMENT — 3px lines per spec
    // ========================================
    else if (patternType.includes('head') && patternType.includes('shoulder')) {
      const shouldersLine = pattern.lines?.find(l => l.name === 'shoulders');
      const headPoint = pattern.lines?.find(l => l.name === 'head');
      const necklineLine = pattern.lines?.find(l => l.name === 'neckline');
      
      // Connect shoulders and head - THICK lines
      if (shouldersLine?.points?.length >= 2 || headPoint?.points) {
        const hsSeries = chart.addSeries(LineSeries, {
          color: PATTERN_COLORS.doubleHighs,
          lineWidth: 3,  // Increased to 3px per spec
          lineStyle: 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        
        const allPoints = dedupeByTime([
          ...(shouldersLine?.points || []),
          ...(headPoint?.points || []),
        ].map(p => ({ time: normalizeTime(p.time), value: p.value })));
        
        if (allPoints.length >= 2) {
          hsSeries.setData(allPoints);
          seriesList.push(hsSeries);
        }
      }
      
      // Neckline - prominent, solid
      if (necklineLine?.points?.length >= 2) {
        const neckSeries = chart.addSeries(LineSeries, {
          color: PATTERN_COLORS.neckline,
          lineWidth: 3,  // Increased to 3px per spec
          lineStyle: 0,  // Solid, not dashed
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        neckSeries.setData(dedupeByTime(necklineLine.points.map(p => ({
          time: normalizeTime(p.time),
          value: p.value,
        }))));
        seriesList.push(neckSeries);
      }
    }
    
    // ========================================
    // WEDGE (Rising, Falling)
    // PRIMARY VISUAL ELEMENT — 3px lines per spec
    // ========================================
    else if (patternType.includes('wedge')) {
      const upperLine = pattern.lines?.find(l => l.name === 'upper');
      const lowerLine = pattern.lines?.find(l => l.name === 'lower');
      
      if (upperLine?.points?.length >= 2) {
        const upperSeries = chart.addSeries(LineSeries, {
          color: PATTERN_COLORS.upperTrendline,
          lineWidth: 3,  // Increased to 3px per spec
          lineStyle: 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        upperSeries.setData(dedupeByTime(upperLine.points.map(p => ({
          time: normalizeTime(p.time),
          value: p.value,
        }))));
        seriesList.push(upperSeries);
      }
      
      if (lowerLine?.points?.length >= 2) {
        const lowerSeries = chart.addSeries(LineSeries, {
          color: PATTERN_COLORS.lowerTrendline,
          lineWidth: 3,  // Increased to 3px per spec
          lineStyle: 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        lowerSeries.setData(dedupeByTime(lowerLine.points.map(p => ({
          time: normalizeTime(p.time),
          value: p.value,
        }))));
        seriesList.push(lowerSeries);
      }
    }
    
    // ========================================
    // BREAKOUT & INVALIDATION LEVELS
    // ========================================
    if (pattern.breakout_level) {
      const breakoutSeries = chart.addSeries(LineSeries, {
        color: '#22c55e',
        lineWidth: 2,
        lineStyle: 0, // Solid - important level
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      breakoutSeries.setData([
        { time: normalizeTime(endTime || startTime), value: pattern.breakout_level },
        { time: normalizeTime(lastTime), value: pattern.breakout_level },
      ]);
      seriesList.push(breakoutSeries);
    }
    
    if (pattern.invalidation) {
      const invalSeries = chart.addSeries(LineSeries, {
        color: '#ef4444',
        lineWidth: 2,
        lineStyle: 2, // Dashed
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      invalSeries.setData([
        { time: normalizeTime(endTime || startTime), value: pattern.invalidation },
        { time: normalizeTime(lastTime), value: pattern.invalidation },
      ]);
      seriesList.push(invalSeries);
    }
    
    // ========================================
    // EXECUTION LEVELS — Entry, Stop, Targets (NEW!)
    // ========================================
    // Execution is part of pattern, not a separate layer
    const execution = derivePatternExecution(pattern, pattern.direction_bias || pattern.direction);
    
    if (execution) {
      // Entry Zone (horizontal line at entry)
      if (execution.entry_zone?.[0]) {
        const entrySeries = chart.addSeries(LineSeries, {
          color: PATTERN_COLORS.entryLine,
          lineWidth: 2,
          lineStyle: 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        entrySeries.setData([
          { time: normalizeTime(endTime || startTime), value: execution.entry_zone[0] },
          { time: normalizeTime(lastTime), value: execution.entry_zone[0] },
        ]);
        seriesList.push(entrySeries);
      }
      
      // Stop Loss
      if (execution.stop) {
        const stopSeries = chart.addSeries(LineSeries, {
          color: PATTERN_COLORS.stopLoss,
          lineWidth: 2,
          lineStyle: 1, // Dotted
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        stopSeries.setData([
          { time: normalizeTime(endTime || startTime), value: execution.stop },
          { time: normalizeTime(lastTime), value: execution.stop },
        ]);
        seriesList.push(stopSeries);
      }
      
      // Take Profit 1
      if (execution.tp1) {
        const tp1Series = chart.addSeries(LineSeries, {
          color: PATTERN_COLORS.takeProfit1,
          lineWidth: 2,
          lineStyle: 2, // Dashed
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        tp1Series.setData([
          { time: normalizeTime(endTime || startTime), value: execution.tp1 },
          { time: normalizeTime(lastTime), value: execution.tp1 },
        ]);
        seriesList.push(tp1Series);
      }
      
      // Take Profit 2
      if (execution.tp2) {
        const tp2Series = chart.addSeries(LineSeries, {
          color: PATTERN_COLORS.takeProfit2,
          lineWidth: 1,
          lineStyle: 2, // Dashed
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        tp2Series.setData([
          { time: normalizeTime(endTime || startTime), value: execution.tp2 },
          { time: normalizeTime(lastTime), value: execution.tp2 },
        ]);
        seriesList.push(tp2Series);
      }
    }
    
  } catch (e) {
    console.warn('[PatternGeometryRenderer] Error rendering pattern:', e);
  }
  
  return seriesList;
}

export default { renderPatternGeometry, derivePatternExecution, PATTERN_COLORS };
