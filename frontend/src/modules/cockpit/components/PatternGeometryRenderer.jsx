/**
 * Pattern Geometry Renderer
 * ==========================
 * 
 * UNIVERSAL PATTERN GEOMETRY RENDERER
 * Renders ANY pattern from the Pattern Geometry Contract.
 * Frontend does NOT contain pattern-specific logic.
 * It only renders primitives: segments, levels, zones, markers.
 */

import { LineSeries } from 'lightweight-charts';

export function renderPatternGeometry(chart, patternGeometry, priceSeries, candles) {
  if (!patternGeometry?.geometry) {
    console.log('[PatternRenderer] No geometry in pattern');
    return [];
  }
  
  const { geometry, label, confidence, direction } = patternGeometry;
  const { segments, levels, zones, markers } = geometry;
  const series = [];
  
  // Helper: normalize time
  const normalizeTime = (t) => t > 1e12 ? Math.floor(t / 1000) : t;
  
  // Style map for segment kinds
  const segmentStyles = {
    resistance: { color: '#ef4444', width: 2 },
    resistance_falling: { color: '#ef4444', width: 2 },
    support: { color: '#16a34a', width: 2 },
    support_rising: { color: '#16a34a', width: 2 },
    neckline: { color: '#f59e0b', width: 2, dashed: true },
    upper_channel: { color: '#a78bfa', width: 1.5 },
    lower_channel: { color: '#a78bfa', width: 1.5 },
    trendline_upper: { color: '#ef4444', width: 1.5 },
    trendline_lower: { color: '#16a34a', width: 1.5 },
    pole: { color: '#3b82f6', width: 2 },
    flag_upper: { color: '#64748b', width: 1.5 },
    flag_lower: { color: '#64748b', width: 1.5 },
  };
  
  // ═══════════════════════════════════════════════════════════════
  // 1. RENDER SEGMENTS (trendlines, boundaries)
  // ═══════════════════════════════════════════════════════════════
  if (segments?.length > 0) {
    segments.forEach((seg, idx) => {
      if (!seg.points || seg.points.length < 2) return;
      
      const style = segmentStyles[seg.kind] || { color: '#64748b', width: 1.5 };
      const color = seg.color || style.color;
      
      // Sort and normalize points
      const sortedPoints = seg.points
        .map(p => ({ time: normalizeTime(p.time), value: p.price }))
        .sort((a, b) => a.time - b.time);
      
      // Skip if times are same
      if (sortedPoints[0].time === sortedPoints[sortedPoints.length - 1].time) return;
      
      try {
        const lineSeries = chart.addSeries(LineSeries, {
          color: color,
          lineWidth: style.width || 2,
          lineStyle: style.dashed ? 2 : 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        lineSeries.setData(sortedPoints);
        series.push(lineSeries);
        console.log(`[PatternRenderer] Segment ${seg.kind}: ${sortedPoints.length} points`);
      } catch (e) {
        console.warn(`[PatternRenderer] Failed to render segment ${seg.kind}:`, e.message);
      }
    });
  }
  
  // ═══════════════════════════════════════════════════════════════
  // 2. RENDER LEVELS (breakout, invalidation, neckline)
  // ═══════════════════════════════════════════════════════════════
  if (levels?.length > 0 && priceSeries) {
    levels.forEach(level => {
      const lineStyleMap = {
        dashed: 2,
        dotted: 1,
        solid: 0,
      };
      
      const colorMap = {
        breakout: '#16a34a',
        invalidation: '#ef4444',
        neckline: '#f59e0b',
        target: '#3b82f6',
      };
      
      try {
        priceSeries.createPriceLine({
          price: level.price,
          color: level.color || colorMap[level.kind] || '#64748b',
          lineWidth: 1.5,
          lineStyle: lineStyleMap[level.style] ?? 2,
          axisLabelVisible: true,
          title: level.label || level.kind?.toUpperCase() || '',
        });
        console.log(`[PatternRenderer] Level ${level.kind}: ${level.price}`);
      } catch (e) {
        console.warn(`[PatternRenderer] Failed to render level ${level.kind}:`, e.message);
      }
    });
  }
  
  // ═══════════════════════════════════════════════════════════════
  // 3. RENDER ZONES (pattern area, apex zone)
  // ═══════════════════════════════════════════════════════════════
  // Zones would use AreaSeries — skip for now as they're optional
  
  // ═══════════════════════════════════════════════════════════════
  // 4. RENDER MARKERS (anchor points, peaks, shoulders)
  // ═══════════════════════════════════════════════════════════════
  if (markers?.length > 0 && priceSeries) {
    const chartMarkers = markers.map(m => ({
      time: normalizeTime(m.time),
      position: 'aboveBar',
      color: direction === 'bullish' ? '#16a34a' : 
             direction === 'bearish' ? '#ef4444' : '#3b82f6',
      shape: 'circle',
      text: m.label || '',
      size: 0.5,
    }));
    
    try {
      // Sort by time before setting
      chartMarkers.sort((a, b) => a.time - b.time);
      priceSeries.setMarkers(chartMarkers);
      console.log(`[PatternRenderer] Markers: ${chartMarkers.length}`);
    } catch (e) {
      console.warn('[PatternRenderer] Failed to render markers:', e.message);
    }
  }
  
  console.log(`[PatternRenderer] Rendered: ${label || 'Unknown'} (${(confidence || 0) * 100}% confidence)`);
  return series;
}

export default renderPatternGeometry;
