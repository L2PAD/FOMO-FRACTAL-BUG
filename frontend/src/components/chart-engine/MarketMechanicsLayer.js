/**
 * MarketMechanicsLayer — Visualization for Market Mechanics Engine
 * ================================================================
 * 
 * Renders on chart:
 * 1. POI zones (demand/supply order blocks) — rectangles
 * 2. Liquidity lines (EQH/EQL) — thin dashed lines
 * 3. Sweep markers (BSL/SSL) — arrows
 * 4. CHOCH validation labels (VALID/FAKE)
 * 5. Displacement highlights (optional)
 * 
 * Rules:
 * - Maximum 5-7 elements on chart
 * - Each element must influence decision
 * - No visual noise
 * - POI visible immediately
 */

import { LineSeries, AreaSeries, createSeriesMarkers } from 'lightweight-charts';

// ═══════════════════════════════════════════════════════════════
// COLORS — Market Mechanics Palette
// ═══════════════════════════════════════════════════════════════

export const MM_COLORS = {
  // POI Zones - ENHANCED visibility per user spec (opacity 0.2-0.3)
  demandActive: 'rgba(34, 197, 94, 0.25)',      // Green, MORE visible
  demandMitigated: 'rgba(34, 197, 94, 0.08)',   // Green, faded
  supplyActive: 'rgba(239, 68, 68, 0.25)',      // Red, MORE visible
  supplyMitigated: 'rgba(239, 68, 68, 0.08)',   // Red, faded
  demandBorder: '#22c55e',
  supplyBorder: '#ef4444',
  
  // Liquidity - slightly more visible
  eqh: 'rgba(239, 68, 68, 0.45)',               // Red-orange for highs
  eql: 'rgba(34, 197, 94, 0.45)',               // Green for lows
  
  // Sweeps
  bslSweep: '#ef4444',                           // Red - bearish signal
  sslSweep: '#22c55e',                           // Green - bullish signal
  
  // CHOCH
  chochValid: '#22c55e',
  chochWeak: '#f59e0b',
  chochFake: '#6b7280',
  
  // Displacement - slightly more visible
  bullishDisplacement: 'rgba(34, 197, 94, 0.08)',
  bearishDisplacement: 'rgba(239, 68, 68, 0.08)',
};

// ═══════════════════════════════════════════════════════════════
// MARKET MECHANICS RENDERER
// ═══════════════════════════════════════════════════════════════

export class MarketMechanicsRenderer {
  constructor(chart, priceSeries) {
    this.chart = chart;
    this.priceSeries = priceSeries;
    this.renderedSeries = [];
    this.renderedPriceLines = [];
    this.disposed = false;
  }

  /**
   * Check if chart is still valid
   */
  isValid() {
    return !this.disposed && this.chart && this.priceSeries;
  }

  /**
   * Clear all rendered market mechanics elements
   */
  clear() {
    this.disposed = true;
    
    // Remove series
    this.renderedSeries.forEach(series => {
      try {
        if (series && this.chart) {
          this.chart.removeSeries(series);
        }
      } catch (e) {
        // Ignore errors during cleanup
      }
    });
    this.renderedSeries = [];
    
    // Remove price lines
    this.renderedPriceLines.forEach(line => {
      try {
        if (line && this.priceSeries) {
          this.priceSeries.removePriceLine(line);
        }
      } catch (e) {
        // Ignore errors during cleanup
      }
    });
    this.renderedPriceLines = [];
    
    // Clear references
    this.chart = null;
    this.priceSeries = null;
  }

  /**
   * Render all market mechanics layers
   */
  render(data, options = {}) {
    // Check if chart is still valid
    if (!this.isValid()) {
      console.warn('MarketMechanicsRenderer: Chart is disposed, skipping render');
      return;
    }

    const {
      showPOI = true,
      showLiquidity = true,
      showSweeps = true,
      showCHOCH = true,
      maxPOIZones = 3,
      maxLiquidityLines = 4,
      maxSweeps = 2,
    } = options;

    const { poi, liquidity, chochValidation, displacement, candles } = data;

    // Get time range for zones
    const timeRange = this._getTimeRange(candles);

    // Render in correct z-order (back to front)
    if (showPOI && poi?.zones) {
      this.renderPOIZones(poi.zones, timeRange, maxPOIZones);
    }

    if (showLiquidity && liquidity) {
      this.renderLiquidityLines(liquidity, maxLiquidityLines);
    }

    // Collect markers for sweeps and CHOCH
    const markers = [];

    if (showSweeps && liquidity?.sweeps) {
      this._addSweepMarkers(markers, liquidity.sweeps, maxSweeps);
    }

    if (showCHOCH && chochValidation) {
      this._addCHOCHMarker(markers, chochValidation);
    }

    // Render displacement events (impulse moves)
    if (displacement?.events && candles) {
      this.renderDisplacementEvents(displacement.events, candles, timeRange);
    }

    // Apply all markers
    if (markers.length > 0) {
      markers.sort((a, b) => a.time - b.time);
      this._setMarkers(markers);
    }
  }

  // ═══════════════════════════════════════════════════════════════
  // DISPLACEMENT EVENTS — Impulse Moves
  // ═══════════════════════════════════════════════════════════════
  
  renderDisplacementEvents(events, candles, timeRange) {
    if (!this.isValid() || !events || events.length === 0) return;
    
    // Only show strongest displacement events (max 3)
    const strongEvents = [...events]
      .filter(e => e.impulse === true)
      .slice(0, 3);
    
    strongEvents.forEach(event => {
      const isBullish = event.direction === 'bullish';
      const color = isBullish ? MM_COLORS.bullishDisplacement : MM_COLORS.bearishDisplacement;
      const borderColor = isBullish ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)';
      
      // Get time range for this displacement
      const startIdx = event.start_index || 0;
      const endIdx = event.end_index || startIdx + 3;
      
      if (startIdx >= 0 && endIdx < candles.length) {
        const startTime = candles[startIdx]?.time;
        const endTime = candles[endIdx]?.time;
        
        // Get price range
        const displacementCandles = candles.slice(startIdx, endIdx + 1);
        const high = Math.max(...displacementCandles.map(c => c.high));
        const low = Math.min(...displacementCandles.map(c => c.low));
        
        if (startTime && endTime && high > 0 && low > 0) {
          // Render as area highlight
          const areaSeries = this.chart.addSeries(AreaSeries, {
            lineColor: borderColor,
            topColor: color,
            bottomColor: color,
            lineWidth: 1,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          
          // Create simple area data
          areaSeries.setData([
            { time: startTime, value: high },
            { time: endTime, value: high },
          ]);
          this.renderedSeries.push(areaSeries);
        }
      }
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // POI ZONES — Order Blocks / Supply / Demand
  // ═══════════════════════════════════════════════════════════════

  renderPOIZones(zones, timeRange, maxZones = 3) {
    if (!zones || zones.length === 0) return;

    // Prioritize active zones, then by strength
    const sortedZones = [...zones]
      .sort((a, b) => {
        // Active zones first
        if (!a.mitigated && b.mitigated) return -1;
        if (a.mitigated && !b.mitigated) return 1;
        // Then by strength
        return (b.strength || 0) - (a.strength || 0);
      })
      .slice(0, maxZones);

    sortedZones.forEach(zone => {
      this._renderPOIZone(zone, timeRange);
    });
  }

  _renderPOIZone(zone, timeRange) {
    // Safety check
    if (!this.isValid()) return;
    
    const isDemand = zone.type === 'demand';
    const isActive = !zone.mitigated;
    
    const color = isDemand
      ? (isActive ? MM_COLORS.demandActive : MM_COLORS.demandMitigated)
      : (isActive ? MM_COLORS.supplyActive : MM_COLORS.supplyMitigated);
    
    const borderColor = isDemand ? MM_COLORS.demandBorder : MM_COLORS.supplyBorder;

    // Calculate zone time bounds
    const startTime = zone.origin_time || timeRange.start;
    const endTime = timeRange.end;

    // Render zone as area series (workaround for lightweight-charts)
    // Top boundary line - THICKER for active zones
    const topSeries = this.chart.addSeries(LineSeries, {
      color: isActive ? borderColor : 'transparent',
      lineWidth: isActive ? 2 : 0,  // Increased from 1 to 2
      lineStyle: 0, // Solid for active, was dashed
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    // Create data points spanning the zone
    const zoneData = [
      { time: startTime, value: zone.price_high },
      { time: endTime, value: zone.price_high },
    ];
    
    topSeries.setData(zoneData);
    this.renderedSeries.push(topSeries);

    // Bottom boundary - THICKER for active zones
    const bottomSeries = this.chart.addSeries(LineSeries, {
      color: isActive ? borderColor : 'transparent',
      lineWidth: isActive ? 2 : 0,  // Increased from 1 to 2
      lineStyle: 0, // Solid for active
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    bottomSeries.setData([
      { time: startTime, value: zone.price_low },
      { time: endTime, value: zone.price_low },
    ]);
    this.renderedSeries.push(bottomSeries);

    // Fill area between lines
    const areaSeries = this.chart.addSeries(AreaSeries, {
      lineColor: 'transparent',
      topColor: color,
      bottomColor: color,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    areaSeries.setData([
      { time: startTime, value: zone.price_high },
      { time: endTime, value: zone.price_high },
    ]);
    this.renderedSeries.push(areaSeries);

    // Add label as price line - ALWAYS show label with DEMAND/SUPPLY text
    const zoneLabel = isDemand ? 'DEMAND' : 'SUPPLY';
    const statusLabel = isActive ? '' : ' (MIT)';  // Mitigated indicator
    
    const label = this.priceSeries.createPriceLine({
      price: zone.price_mid || (zone.price_high + zone.price_low) / 2,
      color: isActive ? borderColor : 'rgba(100, 116, 139, 0.5)',
      lineWidth: 0,
      lineStyle: 2,
      axisLabelVisible: true,
      title: `${zoneLabel}${statusLabel}`,
    });
    this.renderedPriceLines.push(label);
  }

  // ═══════════════════════════════════════════════════════════════
  // LIQUIDITY LINES — EQH / EQL
  // ═══════════════════════════════════════════════════════════════

  renderLiquidityLines(liquidity, maxLines = 4) {
    // Safety check
    if (!this.isValid()) return;
    
    const pools = liquidity.pools || [];
    
    // Include active and recently taken pools (they're still relevant)
    const relevantPools = pools
      .filter(p => (p.strength || 0) >= 1.5 && (p.status === 'active' || p.status === 'taken'))
      .sort((a, b) => (b.strength || 0) - (a.strength || 0))
      .slice(0, maxLines);

    relevantPools.forEach(pool => {
      const isHigh = pool.side === 'high';
      const color = isHigh ? MM_COLORS.eqh : MM_COLORS.eql;
      const label = isHigh ? 'EQH' : 'EQL';
      const status = pool.status === 'taken' ? '✓' : '';

      const priceLine = this.priceSeries.createPriceLine({
        price: pool.price,
        color: color,
        lineWidth: 1,
        lineStyle: pool.status === 'taken' ? 1 : 2, // Dotted if taken, dashed if active
        axisLabelVisible: true,
        title: `${label}${status} (${pool.touches || '?'})`,
      });
      
      this.renderedPriceLines.push(priceLine);
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // SWEEP MARKERS — BSL / SSL
  // ═══════════════════════════════════════════════════════════════

  _addSweepMarkers(markers, sweeps, maxSweeps = 2) {
    if (!sweeps || sweeps.length === 0) return;

    // Get strongest sweeps only
    const strongSweeps = [...sweeps]
      .sort((a, b) => (b.strength || 0) - (a.strength || 0))
      .slice(0, maxSweeps);

    strongSweeps.forEach(sweep => {
      const isBSL = sweep.type === 'buy_side_sweep';
      
      markers.push({
        time: sweep.time,
        position: isBSL ? 'aboveBar' : 'belowBar',
        color: isBSL ? MM_COLORS.bslSweep : MM_COLORS.sslSweep,
        shape: isBSL ? 'arrowDown' : 'arrowUp',
        text: isBSL ? 'BSL' : 'SSL',
      });
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // CHOCH VALIDATION MARKER
  // ═══════════════════════════════════════════════════════════════

  _addCHOCHMarker(markers, chochValidation) {
    if (!chochValidation) return;
    
    // Need either event_time or we can derive from candle_index
    const eventTime = chochValidation.event_time || chochValidation.candle_time;
    if (!eventTime) return;

    const { is_valid, label, direction, score } = chochValidation;
    
    // Determine color based on validation
    let color;
    let text;
    
    if (is_valid) {
      color = MM_COLORS.chochValid;
      text = 'CHOCH ✓';
    } else if (score >= 0.45) {
      color = MM_COLORS.chochWeak;
      text = 'CHOCH?';
    } else {
      color = MM_COLORS.chochFake;
      text = 'CHOCH ✗';
    }

    const isBullish = direction === 'bullish';

    markers.push({
      time: eventTime,
      position: isBullish ? 'belowBar' : 'aboveBar',
      color: color,
      shape: isBullish ? 'arrowUp' : 'arrowDown',
      text: text,
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // HELPERS
  // ═══════════════════════════════════════════════════════════════

  _getTimeRange(candles) {
    if (!candles || candles.length === 0) {
      return { start: 0, end: 0 };
    }
    const times = candles.map(c => c.time).filter(t => t > 0);
    return {
      start: Math.min(...times),
      end: Math.max(...times),
    };
  }

  _setMarkers(markers) {
    try {
      // Import already available at top of file
      createSeriesMarkers(this.priceSeries, markers);
    } catch (e) {
      console.warn('Failed to set markers:', e);
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// EXPORT HELPER FUNCTION
// ═══════════════════════════════════════════════════════════════

/**
 * Render market mechanics on existing chart
 * 
 * @param {Object} chart - lightweight-charts instance
 * @param {Object} priceSeries - main price series
 * @param {Object} data - { poi, liquidity, chochValidation, displacement, candles }
 * @param {Object} options - rendering options
 * @returns {MarketMechanicsRenderer} renderer instance for cleanup
 */
export function renderMarketMechanics(chart, priceSeries, data, options = {}) {
  const renderer = new MarketMechanicsRenderer(chart, priceSeries);
  renderer.render(data, options);
  return renderer;
}

export default MarketMechanicsRenderer;
