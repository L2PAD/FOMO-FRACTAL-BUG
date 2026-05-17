/**
 * ChartObjectRenderer — PHASE F4.1
 * 
 * Renders backend ChartObject[] on TradingView Lightweight Charts
 * 
 * Supported object types:
 * - Patterns: triangle, channel, wedge, breakout
 * - Levels: support_cluster, resistance_cluster, liquidity_zone
 * - Hypothesis: hypothesis_path, entry_zone, stop_loss, take_profit
 * - Fractals: fractal_projection, fractal_reference
 * - Indicators: ema_series, sma_series, bollinger_band
 */

import { LineSeries, AreaSeries } from 'lightweight-charts';

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

const OBJECT_COLORS = {
  // Patterns - subtle, not dominant
  triangle_symmetric: 'rgba(59, 130, 246, 0.7)',
  triangle_ascending: 'rgba(34, 197, 94, 0.7)',
  triangle_descending: 'rgba(239, 68, 68, 0.7)',
  channel_ascending: 'rgba(34, 197, 94, 0.6)',
  channel_descending: 'rgba(239, 68, 68, 0.6)',
  channel_horizontal: 'rgba(107, 114, 128, 0.5)',
  breakout: 'rgba(245, 158, 11, 0.7)',
  compression: 'rgba(139, 92, 246, 0.6)',
  
  // Levels - LEGACY STYLE: thin, dashed, semi-transparent, secondary
  support_cluster: 'rgba(34, 197, 94, 0.45)',      // Light green, low opacity
  resistance_cluster: 'rgba(239, 68, 68, 0.45)',   // Light red, low opacity
  liquidity_zone: 'rgba(59, 130, 246, 0.35)',      // Light blue, very low opacity
  invalidation_line: 'rgba(239, 68, 68, 0.5)',
  
  // Hypothesis
  hypothesis_path: '#22C55E',
  entry_zone: '#3B82F6',
  stop_loss: '#EF4444',
  take_profit: '#22C55E',
  confidence_band: 'rgba(34, 197, 94, 0.15)',
  
  // Fractals
  fractal_projection: '#8B5CF6',
  fractal_reference: '#6B7280',
  
  // Indicators
  ema_series: '#F59E0B',
  sma_series: '#3B82F6',
  bollinger_upper: '#6B7280',
  bollinger_lower: '#6B7280',
  bollinger_middle: '#8B5CF6',
};

// ═══════════════════════════════════════════════════════════════
// MAIN RENDERER CLASS
// ═══════════════════════════════════════════════════════════════

export class ChartObjectRenderer {
  constructor(chart) {
    this.chart = chart;
    this.seriesMap = new Map(); // id -> series reference
    this.primitiveMap = new Map(); // id -> primitive reference
  }
  
  /**
   * Clear all rendered objects
   */
  clearAll() {
    this.seriesMap.forEach((series, id) => {
      try {
        this.chart.removeSeries(series);
      } catch (e) {
        console.warn(`Failed to remove series ${id}:`, e);
      }
    });
    this.seriesMap.clear();
    this.primitiveMap.clear();
  }
  
  /**
   * Render all objects from backend payload
   */
  renderObjects(objects = [], options = {}) {
    const { sortByPriority = true, maxObjects = 50 } = options;
    
    // Sort by priority (high first)
    let sorted = [...objects];
    if (sortByPriority) {
      sorted.sort((a, b) => (b.priority || 0) - (a.priority || 0));
    }
    
    // Limit objects
    sorted = sorted.slice(0, maxObjects);
    
    // Render each object
    sorted.forEach(obj => {
      try {
        this.renderObject(obj);
      } catch (e) {
        console.warn(`Failed to render object ${obj.id}:`, e);
      }
    });
  }
  
  /**
   * Render single object by type
   */
  renderObject(obj) {
    const { type, id } = obj;
    
    // Skip if already rendered
    if (this.seriesMap.has(id) || this.primitiveMap.has(id)) {
      return;
    }
    
    switch (type) {
      // Patterns
      case 'triangle_symmetric':
      case 'triangle_ascending':
      case 'triangle_descending':
        return this.renderTriangle(obj);
        
      case 'channel_ascending':
      case 'channel_descending':
      case 'channel_horizontal':
      case 'channel':
        return this.renderChannel(obj);
        
      case 'breakout':
      case 'breakout_zone':
        return this.renderBreakoutZone(obj);
        
      case 'compression':
        return this.renderCompression(obj);
        
      // Advanced Patterns
      case 'head_shoulders':
      case 'head_shoulders_inverse':
        return this.renderHeadShoulders(obj);
        
      case 'double_top':
      case 'double_bottom':
        return this.renderDoubleTopBottom(obj);
        
      case 'cup_handle':
        return this.renderCupHandle(obj);
        
      case 'wedge_rising':
      case 'wedge_falling':
        return this.renderWedge(obj);
        
      case 'harmonic_gartley':
      case 'harmonic_bat':
        return this.renderHarmonic(obj);
        
      // Levels
      case 'support_cluster':
      case 'resistance_cluster':
        return this.renderHorizontalLevel(obj);
        
      case 'liquidity_zone':
        return this.renderZone(obj);
        
      case 'invalidation_line':
        return this.renderInvalidationLine(obj);
        
      // Hypothesis
      case 'hypothesis_path':
        return this.renderHypothesisPath(obj);
        
      case 'entry_zone':
        return this.renderEntryZone(obj);
        
      case 'stop_loss':
        return this.renderStopLoss(obj);
        
      case 'take_profit':
        return this.renderTakeProfit(obj);
        
      case 'confidence_corridor':
        return this.renderConfidenceBand(obj);
        
      // Fractals
      case 'fractal_projection':
        return this.renderFractalProjection(obj);
        
      case 'fractal_reference':
        return this.renderFractalReference(obj);
        
      // Indicators
      case 'ema_series':
      case 'sma_series':
        return this.renderIndicatorLine(obj);
        
      case 'bollinger_band':
      case 'donchian_channel':
      case 'keltner_channel':
        return this.renderBollingerBand(obj);  // Same band rendering
        
      case 'ichimoku_cloud':
        return this.renderIchimokuCloud(obj);
        
      case 'psar_series':
        return this.renderPSAR(obj);
        
      case 'cci_series':
      case 'williams_r_series':
      case 'rsi_series':
      case 'atr_series':
      case 'atr_band':
      case 'macd_series':
      case 'volume_profile':
        // These need separate pane - skip for now
        console.log(`Indicator ${type} requires separate pane, skipping`);
        return;
        
      default:
        console.warn(`Unknown object type: ${type}`);
    }
  }
  
  // ═══════════════════════════════════════════════════════════════
  // PATTERN RENDERERS
  // ═══════════════════════════════════════════════════════════════
  
  renderTriangle(obj) {
    const { id, type, points, style, confidence } = obj;
    const color = style?.color || OBJECT_COLORS[type] || '#3B82F6';
    const opacity = confidence || 0.7;
    
    if (!points || points.length < 3) return;
    
    // Triangle has 3+ points forming upper and lower trendlines
    // Upper line: points[0] -> points[1]
    // Lower line: points[2] -> points[3] (or apex)
    
    // Render as two line series
    const upperSeries = this.chart.addSeries(LineSeries, {
      color: color,
      lineWidth: 2,
      lineStyle: 0, // Solid
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    
    const upperData = points.slice(0, 2).map(p => ({
      time: this._parseTime(p.timestamp),
      value: p.price,
    }));
    upperSeries.setData(upperData);
    
    this.seriesMap.set(`${id}_upper`, upperSeries);
    
    if (points.length >= 4) {
      const lowerSeries = this.chart.addSeries(LineSeries, {
        color: color,
        lineWidth: 2,
        lineStyle: 0,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      
      const lowerData = points.slice(2, 4).map(p => ({
        time: this._parseTime(p.timestamp),
        value: p.price,
      }));
      lowerSeries.setData(lowerData);
      
      this.seriesMap.set(`${id}_lower`, lowerSeries);
    }
  }
  
  renderChannel(obj) {
    const { id, type, points, upper_band, lower_band, timestamps, style, confidence } = obj;
    const color = style?.color || OBJECT_COLORS[type] || '#3B82F6';
    
    // Channel can have upper_band/lower_band arrays or points
    if (upper_band && lower_band && timestamps) {
      // Band format
      const upperSeries = this.chart.addSeries(LineSeries, {
        color: color,
        lineWidth: 1,
        lineStyle: 2, // Dashed
        priceLineVisible: false,
        lastValueVisible: false,
      });
      
      const upperData = timestamps.map((t, i) => ({
        time: this._parseTime(t),
        value: upper_band[i],
      }));
      upperSeries.setData(upperData);
      this.seriesMap.set(`${id}_upper`, upperSeries);
      
      const lowerSeries = this.chart.addSeries(LineSeries, {
        color: color,
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      
      const lowerData = timestamps.map((t, i) => ({
        time: this._parseTime(t),
        value: lower_band[i],
      }));
      lowerSeries.setData(lowerData);
      this.seriesMap.set(`${id}_lower`, lowerSeries);
    } else if (points && points.length >= 4) {
      // Points format
      this.renderTriangle(obj); // Same logic
    }
  }
  
  renderBreakoutZone(obj) {
    const { id, points, style } = obj;
    const color = style?.color || OBJECT_COLORS.breakout;
    
    if (!points || points.length < 2) return;
    
    // Breakout zone as horizontal area
    const series = this.chart.addSeries(LineSeries, {
      color: color,
      lineWidth: 2,
      lineStyle: 1, // Dotted
      priceLineVisible: false,
      lastValueVisible: false,
    });
    
    const data = points.map(p => ({
      time: this._parseTime(p.timestamp),
      value: p.price,
    }));
    series.setData(data);
    this.seriesMap.set(id, series);
  }
  
  renderCompression(obj) {
    // Same as breakout zone but different color
    this.renderBreakoutZone({ ...obj, style: { color: OBJECT_COLORS.compression } });
  }
  
  // ═══════════════════════════════════════════════════════════════
  // LEVEL RENDERERS
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * LEGACY STYLE: Thin, dashed, semi-transparent horizontal levels
   * These are CONTEXT, not primary signals - should be visually secondary
   */
  renderHorizontalLevel(obj) {
    const { id, type, points, metadata, style, confidence } = obj;
    const isSupport = type === 'support_cluster';
    const color = style?.color || (isSupport ? OBJECT_COLORS.support_cluster : OBJECT_COLORS.resistance_cluster);
    
    // Get price from points or metadata
    const price = points?.[0]?.price || metadata?.price_center || metadata?.price;
    if (!price) return;
    
    // LEGACY STYLE: thin dotted line, NO price line visible (keeps it secondary)
    const series = this.chart.addSeries(LineSeries, {
      color: color,
      lineWidth: 1,           // Thin
      lineStyle: 1,           // 1 = Dotted (more subtle than dashed)
      priceLineVisible: false, // NO price line - keeps it secondary
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    
    // Extend line across visible range
    const now = Math.floor(Date.now() / 1000);
    const past = now - 90 * 24 * 60 * 60; // 90 days ago for better coverage
    
    series.setData([
      { time: past, value: price },
      { time: now, value: price },
    ]);
    
    this.seriesMap.set(id, series);
  }
  
  /**
   * LEGACY STYLE: Liquidity zones - very subtle, semi-transparent
   */
  renderZone(obj) {
    const { id, type, metadata, style, confidence } = obj;
    const color = style?.color || OBJECT_COLORS.liquidity_zone;
    
    const priceHigh = metadata?.price_high || metadata?.upper;
    const priceLow = metadata?.price_low || metadata?.lower;
    
    if (!priceHigh || !priceLow) return;
    
    // LEGACY STYLE: thin dotted boundaries, very low opacity
    const now = Math.floor(Date.now() / 1000);
    const past = now - 90 * 24 * 60 * 60;
    
    // Upper boundary - dotted, thin
    const upperSeries = this.chart.addSeries(LineSeries, {
      color: color,
      lineWidth: 1,
      lineStyle: 1, // Dotted
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    
    upperSeries.setData([
      { time: past, value: priceHigh },
      { time: now, value: priceHigh },
    ]);
    this.seriesMap.set(`${id}_upper`, upperSeries);
    
    // Lower boundary - dotted, thin
    const lowerSeries = this.chart.addSeries(LineSeries, {
      color: color,
      lineWidth: 1,
      lineStyle: 1, // Dotted
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    
    lowerSeries.setData([
      { time: past, value: priceLow },
      { time: now, value: priceLow },
    ]);
    this.seriesMap.set(`${id}_lower`, lowerSeries);
  }
  
  renderInvalidationLine(obj) {
    this.renderHorizontalLevel({
      ...obj,
      type: 'resistance_cluster',
      style: { color: OBJECT_COLORS.invalidation_line },
    });
  }
  
  // ═══════════════════════════════════════════════════════════════
  // HYPOTHESIS RENDERERS
  // ═══════════════════════════════════════════════════════════════
  
  renderHypothesisPath(obj) {
    const { id, points, upper_band, lower_band, timestamps, style, metadata } = obj;
    const color = style?.color || metadata?.color || OBJECT_COLORS.hypothesis_path;
    
    // Main path line
    if (points && points.length > 0) {
      const series = this.chart.addSeries(LineSeries, {
        color: color,
        lineWidth: 2,
        lineStyle: 0, // Solid
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: true,
      });
      
      const data = points.map(p => ({
        time: this._parseTime(p.timestamp),
        value: p.price,
      }));
      series.setData(data);
      this.seriesMap.set(id, series);
    }
    
    // Confidence bands
    if (upper_band && lower_band && timestamps) {
      this.renderConfidenceBand({
        id: `${id}_band`,
        upper_band,
        lower_band,
        timestamps,
        style: { color: color.replace(')', ', 0.15)').replace('rgb', 'rgba') },
      });
    }
  }
  
  renderConfidenceBand(obj) {
    const { id, upper_band, lower_band, timestamps, style } = obj;
    const color = style?.color || OBJECT_COLORS.confidence_band;
    
    if (!upper_band || !lower_band || !timestamps) return;
    
    // Upper line
    const upperSeries = this.chart.addSeries(LineSeries, {
      color: color,
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    
    const upperData = timestamps.map((t, i) => ({
      time: this._parseTime(t),
      value: upper_band[i],
    }));
    upperSeries.setData(upperData);
    this.seriesMap.set(`${id}_upper`, upperSeries);
    
    // Lower line
    const lowerSeries = this.chart.addSeries(LineSeries, {
      color: color,
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    
    const lowerData = timestamps.map((t, i) => ({
      time: this._parseTime(t),
      value: lower_band[i],
    }));
    lowerSeries.setData(lowerData);
    this.seriesMap.set(`${id}_lower`, lowerSeries);
  }
  
  renderEntryZone(obj) {
    const { id, metadata, style } = obj;
    const color = style?.color || OBJECT_COLORS.entry_zone;
    
    const priceHigh = metadata?.entry_high || metadata?.upper;
    const priceLow = metadata?.entry_low || metadata?.lower;
    
    if (priceHigh && priceLow) {
      this.renderZone({
        id,
        metadata: { price_high: priceHigh, price_low: priceLow },
        style: { color },
      });
    }
  }
  
  renderStopLoss(obj) {
    const { id, points, metadata, style } = obj;
    const price = points?.[0]?.price || metadata?.price;
    
    if (!price) return;
    
    this.renderHorizontalLevel({
      id,
      type: 'resistance_cluster',
      points: [{ price }],
      style: { color: OBJECT_COLORS.stop_loss },
    });
  }
  
  renderTakeProfit(obj) {
    const { id, points, metadata, style } = obj;
    
    // Can be single price or array of targets
    const prices = metadata?.targets || [points?.[0]?.price || metadata?.price];
    
    prices.forEach((price, i) => {
      if (!price) return;
      
      this.renderHorizontalLevel({
        id: `${id}_${i}`,
        type: 'support_cluster',
        points: [{ price }],
        style: { color: OBJECT_COLORS.take_profit },
      });
    });
  }
  
  // ═══════════════════════════════════════════════════════════════
  // FRACTAL RENDERERS
  // ═══════════════════════════════════════════════════════════════
  
  renderFractalProjection(obj) {
    const { id, points, style } = obj;
    const color = style?.color || OBJECT_COLORS.fractal_projection;
    
    if (!points || points.length < 2) return;
    
    const series = this.chart.addSeries(LineSeries, {
      color: color,
      lineWidth: 2,
      lineStyle: 2, // Dashed
      priceLineVisible: false,
      lastValueVisible: true,
    });
    
    const data = points.map(p => ({
      time: this._parseTime(p.timestamp),
      value: p.price,
    }));
    series.setData(data);
    this.seriesMap.set(id, series);
  }
  
  renderFractalReference(obj) {
    this.renderFractalProjection({
      ...obj,
      style: { color: OBJECT_COLORS.fractal_reference },
    });
  }
  
  // ═══════════════════════════════════════════════════════════════
  // ADVANCED PATTERN RENDERERS
  // ═══════════════════════════════════════════════════════════════

  renderHeadShoulders(obj) {
    const { id, type, points, style, confidence, metadata } = obj;
    const isInverse = type === 'head_shoulders_inverse';
    const color = isInverse ? '#05A584' : '#E11D48';
    
    if (!points || points.length < 3) return;
    
    // Draw lines connecting shoulders and head
    const lineData = points.map(p => ({
      time: this._parseTime(p.timestamp),
      value: p.price,
    })).sort((a, b) => a.time - b.time);
    
    const series = this.chart.addSeries(LineSeries, {
      color: color,
      lineWidth: 2,
      lineStyle: 0,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    series.setData(lineData);
    this._trackSeries(id, series);
    
    // Draw neckline if available
    if (metadata?.neckline) {
      const necklinePrice = metadata.neckline;
      const now = Math.floor(Date.now() / 1000);
      const past = now - 20 * 24 * 60 * 60;
      
      const neckSeries = this.chart.addSeries(LineSeries, {
        color: color,
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: true,
        lastValueVisible: false,
      });
      neckSeries.setData([
        { time: past, value: necklinePrice },
        { time: now, value: necklinePrice },
      ]);
      this._trackSeries(`${id}_neckline`, neckSeries);
    }
    
    // Add markers for key points
    const markers = points.map(p => ({
      time: this._parseTime(p.timestamp),
      position: isInverse ? 'belowBar' : 'aboveBar',
      color: color,
      shape: 'circle',
      text: (p.type || '').replace('_', ' ').charAt(0).toUpperCase(),
    }));
    series.setMarkers(markers);
  }

  renderDoubleTopBottom(obj) {
    const { id, type, points, style, metadata } = obj;
    const isTop = type === 'double_top';
    const color = isTop ? '#DC2626' : '#059669';
    
    if (!points || points.length < 2) return;
    
    const lineData = points.map(p => ({
      time: this._parseTime(p.timestamp),
      value: p.price,
    })).sort((a, b) => a.time - b.time);
    
    const series = this.chart.addSeries(LineSeries, {
      color: color,
      lineWidth: 2,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    series.setData(lineData);
    this._trackSeries(id, series);
    
    // Neckline
    if (metadata?.neckline) {
      const now = Math.floor(Date.now() / 1000);
      const past = now - 15 * 24 * 60 * 60;
      
      const neckSeries = this.chart.addSeries(LineSeries, {
        color: color,
        lineWidth: 1,
        lineStyle: 1,
        priceLineVisible: true,
        lastValueVisible: false,
      });
      neckSeries.setData([
        { time: past, value: metadata.neckline },
        { time: now, value: metadata.neckline },
      ]);
      this._trackSeries(`${id}_neckline`, neckSeries);
    }
    
    // Markers on peaks/troughs
    const markers = points.map(p => ({
      time: this._parseTime(p.timestamp),
      position: isTop ? 'aboveBar' : 'belowBar',
      color: color,
      shape: isTop ? 'arrowDown' : 'arrowUp',
      text: isTop ? 'DT' : 'DB',
    }));
    series.setMarkers(markers);
  }

  renderCupHandle(obj) {
    const { id, points, style, metadata } = obj;
    const color = style?.color || '#7C3AED';
    
    if (!points || points.length < 3) return;
    
    const lineData = points.map(p => ({
      time: this._parseTime(p.timestamp),
      value: p.price,
    })).sort((a, b) => a.time - b.time);
    
    const series = this.chart.addSeries(LineSeries, {
      color: color,
      lineWidth: 2,
      lineStyle: 0,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    series.setData(lineData);
    this._trackSeries(id, series);
    
    const markers = points.map(p => ({
      time: this._parseTime(p.timestamp),
      position: (p.type || '') === 'cup_bottom' ? 'belowBar' : 'aboveBar',
      color: color,
      shape: 'circle',
      text: (p.type || '').replace('_', ' ').charAt(0).toUpperCase(),
    }));
    series.setMarkers(markers);
  }

  renderWedge(obj) {
    const { id, type, points, style } = obj;
    const isRising = type === 'wedge_rising';
    const color = isRising ? '#F97316' : '#0EA5E9';
    
    if (!points || points.length < 4) return;
    
    // Split into high and low points
    const highPts = points.filter(p => (p.type || '').includes('high'));
    const lowPts = points.filter(p => (p.type || '').includes('low'));
    
    // Upper trendline
    if (highPts.length >= 2) {
      const upperData = highPts.map(p => ({
        time: this._parseTime(p.timestamp),
        value: p.price,
      })).sort((a, b) => a.time - b.time);
      
      const upperSeries = this.chart.addSeries(LineSeries, {
        color: color,
        lineWidth: 2,
        lineStyle: 0,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      upperSeries.setData(upperData);
      this._trackSeries(`${id}_upper`, upperSeries);
    }
    
    // Lower trendline
    if (lowPts.length >= 2) {
      const lowerData = lowPts.map(p => ({
        time: this._parseTime(p.timestamp),
        value: p.price,
      })).sort((a, b) => a.time - b.time);
      
      const lowerSeries = this.chart.addSeries(LineSeries, {
        color: color,
        lineWidth: 2,
        lineStyle: 0,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      lowerSeries.setData(lowerData);
      this._trackSeries(`${id}_lower`, lowerSeries);
    }
  }

  renderHarmonic(obj) {
    const { id, type, points, style, confidence } = obj;
    const color = type === 'harmonic_gartley' ? '#D946EF' : '#A855F7';
    
    if (!points || points.length < 5) return;
    
    // Draw XABCD lines
    const lineData = points.map(p => ({
      time: this._parseTime(p.timestamp),
      value: p.price,
    })).sort((a, b) => a.time - b.time);
    
    const series = this.chart.addSeries(LineSeries, {
      color: color,
      lineWidth: 2,
      lineStyle: 0,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    series.setData(lineData);
    this._trackSeries(id, series);
    
    // Markers for XABCD points
    const labels = ['X', 'A', 'B', 'C', 'D'];
    const markers = points.map((p, i) => ({
      time: this._parseTime(p.timestamp),
      position: i % 2 === 0 ? 'aboveBar' : 'belowBar',
      color: color,
      shape: 'circle',
      text: labels[i] || '',
    }));
    series.setMarkers(markers);
  }

  // ═══════════════════════════════════════════════════════════════
  // NEW INDICATOR RENDERERS
  // ═══════════════════════════════════════════════════════════════

  renderIchimokuCloud(obj) {
    const { id, upper_band, lower_band, middle_band, timestamps, style } = obj;
    
    if (!timestamps || !upper_band || !lower_band) return;
    
    // Tenkan-sen (middle_band)
    if (middle_band && middle_band.length === timestamps.length) {
      const tenkan = this.chart.addSeries(LineSeries, {
        color: '#0EA5E9',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      tenkan.setData(timestamps.map((t, i) => ({
        time: this._parseTime(t),
        value: middle_band[i],
      })).filter(d => d.value != null));
      this._trackSeries(`${id}_tenkan`, tenkan);
    }
    
    // Senkou Span A (upper_band)
    const spanA = this.chart.addSeries(LineSeries, {
      color: 'rgba(5, 150, 105, 0.6)',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    spanA.setData(timestamps.map((t, i) => ({
      time: this._parseTime(t),
      value: upper_band[i],
    })).filter(d => d.value != null));
    this._trackSeries(`${id}_span_a`, spanA);
    
    // Senkou Span B (lower_band)
    const spanB = this.chart.addSeries(LineSeries, {
      color: 'rgba(239, 68, 68, 0.6)',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    spanB.setData(timestamps.map((t, i) => ({
      time: this._parseTime(t),
      value: lower_band[i],
    })).filter(d => d.value != null));
    this._trackSeries(`${id}_span_b`, spanB);
  }

  renderPSAR(obj) {
    const { id, series: values, timestamps, style } = obj;
    const color = style?.color || '#EF4444';
    
    if (!values || !timestamps || values.length !== timestamps.length) return;
    
    // PSAR renders as dots (markers on a hidden line)
    const lineSeries = this.chart.addSeries(LineSeries, {
      color: 'transparent',
      lineWidth: 0,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    
    const data = timestamps.map((t, i) => ({
      time: this._parseTime(t),
      value: values[i],
    })).filter(d => d.value != null);
    
    lineSeries.setData(data);
    
    // Add markers as dots
    const markers = data.map(d => ({
      time: d.time,
      position: 'inBar',
      color: color,
      shape: 'circle',
      text: '',
    }));
    // Only show every 3rd marker to avoid clutter
    lineSeries.setMarkers(markers.filter((_, i) => i % 3 === 0));
    this._trackSeries(id, lineSeries);
  }

  // ═══════════════════════════════════════════════════════════════
  // INDICATOR RENDERERS
  // ═══════════════════════════════════════════════════════════════
  
  renderIndicatorLine(obj) {
    const { id, type, series: values, timestamps, style, metadata } = obj;
    const color = style?.color || OBJECT_COLORS[type] || '#F59E0B';
    
    if (!values || !timestamps || values.length !== timestamps.length) return;
    
    const series = this.chart.addSeries(LineSeries, {
      color: color,
      lineWidth: metadata?.lineWidth || 1,
      lineStyle: 0,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    
    const data = timestamps.map((t, i) => ({
      time: this._parseTime(t),
      value: values[i],
    })).filter(d => d.value !== null && d.value !== undefined);
    
    series.setData(data);
    this.seriesMap.set(id, series);
  }
  
  renderBollingerBand(obj) {
    const { id, upper_band, lower_band, middle_band, timestamps, style } = obj;
    
    if (!timestamps) return;
    
    // Upper band
    if (upper_band) {
      this.renderIndicatorLine({
        id: `${id}_upper`,
        series: upper_band,
        timestamps,
        style: { color: OBJECT_COLORS.bollinger_upper },
      });
    }
    
    // Middle band
    if (middle_band) {
      this.renderIndicatorLine({
        id: `${id}_middle`,
        series: middle_band,
        timestamps,
        style: { color: OBJECT_COLORS.bollinger_middle },
      });
    }
    
    // Lower band
    if (lower_band) {
      this.renderIndicatorLine({
        id: `${id}_lower`,
        series: lower_band,
        timestamps,
        style: { color: OBJECT_COLORS.bollinger_lower },
      });
    }
  }
  
  // ═══════════════════════════════════════════════════════════════
  // UTILITIES
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * Helper to track series in the map
   */
  _trackSeries(id, series) {
    this.seriesMap.set(id, series);
  }
  
  _parseTime(timestamp) {
    if (typeof timestamp === 'number') {
      return timestamp;
    }
    if (typeof timestamp === 'string') {
      // ISO date string
      const date = new Date(timestamp);
      return Math.floor(date.getTime() / 1000);
    }
    return timestamp;
  }
}

export default ChartObjectRenderer;
