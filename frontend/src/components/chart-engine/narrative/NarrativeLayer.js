/**
 * NarrativeLayer — Render market story on chart
 * ==============================================
 * 
 * Renders narrative events as markers and labels on the chart:
 * - Compact badges
 * - Positioned near relevant price points
 * - Connected visually as a chain
 */

import { createSeriesMarkers } from 'lightweight-charts';
import { buildNarrative, hasValidNarrative, getNarrativeSummary } from './NarrativeEngine';

// ═══════════════════════════════════════════════════════════════
// COLORS
// ═══════════════════════════════════════════════════════════════

const NARRATIVE_COLORS = {
  sweep_bearish: '#ef4444',
  sweep_bullish: '#22c55e',
  displacement_bearish: '#f97316',
  displacement_bullish: '#10b981',
  choch_valid: '#22c55e',
  choch_weak: '#f59e0b',
  choch_fake: '#6b7280',
  poi_supply: '#ef4444',
  poi_demand: '#22c55e',
  entry_short: '#ef4444',
  entry_long: '#22c55e',
};

// ═══════════════════════════════════════════════════════════════
// NARRATIVE RENDERER
// ═══════════════════════════════════════════════════════════════

export class NarrativeRenderer {
  constructor(chart, priceSeries) {
    this.chart = chart;
    this.priceSeries = priceSeries;
    this.markers = [];
    this.disposed = false;
  }

  isValid() {
    return !this.disposed && this.chart && this.priceSeries;
  }

  clear() {
    this.disposed = true;
    this.markers = [];
    this.chart = null;
    this.priceSeries = null;
  }

  /**
   * Render narrative on chart
   */
  render(data, candles) {
    if (!this.isValid()) return null;
    if (!candles || candles.length === 0) return null;

    // Build narrative events
    const events = buildNarrative(data);
    
    // Check if we have a valid chain
    if (!hasValidNarrative(events)) {
      // Still show individual events but without "story" markers
      return this._renderMinimalMarkers(events, candles);
    }

    // Render full narrative chain
    return this._renderNarrativeChain(events, candles, data);
  }

  /**
   * Render minimal markers when no valid narrative chain
   */
  _renderMinimalMarkers(events, candles) {
    const markers = [];
    const lastCandle = candles[candles.length - 1];

    events.forEach(event => {
      if (!event.time && event.type === 'entry') {
        event.time = lastCandle.time;
      }

      if (event.time) {
        markers.push({
          time: event.time,
          position: event.markerPosition || 'aboveBar',
          color: event.color,
          shape: event.shape || 'circle',
          text: this._getShortLabel(event),
        });
      }
    });

    this._setMarkers(markers);
    return { events, markers, hasChain: false };
  }

  /**
   * Render full narrative chain with connected events
   */
  _renderNarrativeChain(events, candles, data) {
    const markers = [];
    const lastCandle = candles[candles.length - 1];

    // Map event times to candles for proper positioning
    events.forEach((event, idx) => {
      let time = event.time;
      
      // Find best time for event
      if (!time) {
        if (event.type === 'entry') {
          time = lastCandle.time;
        } else if (event.type === 'displacement' && data.displacement?.last_impulse) {
          time = data.displacement.last_impulse.end_time;
        }
      }

      if (time) {
        markers.push({
          time: time,
          position: event.markerPosition || 'aboveBar',
          color: event.color,
          shape: event.shape || 'circle',
          text: event.label,
        });
      }
    });

    // Sort markers by time
    markers.sort((a, b) => a.time - b.time);

    this._setMarkers(markers);

    // Get summary
    const summary = getNarrativeSummary(events, data.decision);

    return { 
      events, 
      markers, 
      hasChain: true,
      summary,
    };
  }

  /**
   * Get short label for minimal markers
   */
  _getShortLabel(event) {
    switch (event.type) {
      case 'liquidity_sweep':
        return event.subtype === 'buy_side_sweep' ? 'BSL↓' : 'SSL↑';
      case 'displacement':
        return event.direction === 'bearish' ? 'IMP↓' : 'IMP↑';
      case 'choch':
        if (event.isValid) return 'CHOCH✓';
        return event.score >= 0.45 ? 'CHOCH?' : 'CHOCH✗';
      case 'poi':
        return event.subtype === 'supply' ? 'SUPPLY' : 'DEMAND';
      case 'entry':
        return event.subtype === 'short' ? 'SHORT' : 'LONG';
      default:
        return event.label;
    }
  }

  /**
   * Set markers on price series
   */
  _setMarkers(markers) {
    try {
      if (this.priceSeries && markers.length > 0) {
        createSeriesMarkers(this.priceSeries, markers);
      }
    } catch (e) {
      console.warn('NarrativeRenderer: Failed to set markers', e);
    }
  }
}

/**
 * Render narrative on existing chart
 */
export function renderNarrative(chart, priceSeries, data, candles) {
  const renderer = new NarrativeRenderer(chart, priceSeries);
  return renderer.render(data, candles);
}

export default { NarrativeRenderer, renderNarrative };
