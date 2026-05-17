/**
 * ExecutionVisualLayer (EVL)
 * ==========================
 * Renders trade execution overlay DIRECTLY ON CHART.
 * 
 * User should understand entry/stop/target in 1-2 seconds WITHOUT reading panels.
 * 
 * Components:
 * 1. Entry Zone — rectangle (green/red), not a line
 * 2. Stop Loss — thick dashed line
 * 3. TP1 / TP2 — solid/dashed target lines
 * 4. Risk/Reward zones — colored areas between levels
 * 5. R:R badge — small label
 * 
 * Rules:
 * - Only render if setup.valid = true
 * - Only render if price is near entry (within 5%)
 * - 1 chart = 1 action (never multiple setups)
 * - EVL is highest priority visual element
 */

import { LineSeries, AreaSeries } from 'lightweight-charts';

const EVL_COLORS = {
  // Entry
  entryLong: '#22c55e',
  entryShort: '#ef4444',
  entryZoneLong: 'rgba(34, 197, 94, 0.15)',
  entryZoneShort: 'rgba(239, 68, 68, 0.15)',
  
  // Stop
  stop: '#dc2626',
  stopZone: 'rgba(220, 38, 38, 0.1)',
  
  // Targets
  tp1: '#16a34a',
  tp2: '#4ade80',
  rewardZone: 'rgba(34, 197, 94, 0.08)',
  
  // Risk zone
  riskZone: 'rgba(239, 68, 68, 0.08)',
};

/**
 * Check if price is near entry zone (within 5%)
 */
function isNearEntry(currentPrice, entryZone) {
  if (!entryZone || entryZone.length < 2) return false;
  const entryMid = (entryZone[0] + entryZone[1]) / 2;
  const distance = Math.abs(currentPrice - entryMid) / currentPrice;
  return distance < 0.05; // 5% threshold
}

/**
 * Render Execution Visual Layer
 * @param {Object} chart - Lightweight Charts instance
 * @param {Object} priceSeries - Main price series for price lines
 * @param {Object} setup - Trade setup data
 * @param {Array} candles - Candle data for time reference
 * @param {number} currentPrice - Current market price
 */
export function renderExecutionLayer(chart, priceSeries, setup, candles, currentPrice) {
  if (!chart || !priceSeries || !setup) return [];
  if (!setup.valid) return [];
  
  const {
    direction,
    entry_zone,
    stop_loss,
    target_1,
    target_2,
    rr,
  } = setup;
  
  // Check near-price rule
  if (!isNearEntry(currentPrice, entry_zone)) {
    return [];
  }
  
  const isShort = direction === 'short';
  const seriesList = [];
  
  // Get time boundaries for horizontal zones
  const lastCandle = candles[candles.length - 1];
  const firstVisibleCandle = candles[Math.max(0, candles.length - 50)];
  const normalizeTime = (t) => t > 1e12 ? Math.floor(t / 1000) : t;
  const startTime = normalizeTime(firstVisibleCandle?.time || candles[0]?.time);
  const endTime = normalizeTime(lastCandle?.time);
  
  try {
    // ========================================
    // 1. ENTRY ZONE (most prominent)
    // ========================================
    if (entry_zone && entry_zone.length >= 2) {
      const entryHigh = Math.max(...entry_zone);
      const entryLow = Math.min(...entry_zone);
      const entryColor = isShort ? EVL_COLORS.entryShort : EVL_COLORS.entryLong;
      
      // Entry zone upper line
      priceSeries.createPriceLine({
        price: entryHigh,
        color: entryColor,
        lineWidth: 3,
        lineStyle: 0, // Solid
        axisLabelVisible: true,
        title: 'ENTRY',
      });
      
      // Entry zone lower line
      priceSeries.createPriceLine({
        price: entryLow,
        color: entryColor,
        lineWidth: 2,
        lineStyle: 0,
        axisLabelVisible: false,
        title: '',
      });
      
      // Entry zone fill (area between lines)
      // Using horizontal area approximation
      const zoneColor = isShort ? EVL_COLORS.entryZoneShort : EVL_COLORS.entryZoneLong;
      
      // Create filled area for entry zone
      const entryAreaSeries = chart.addSeries(AreaSeries, {
        topColor: zoneColor,
        bottomColor: 'transparent',
        lineColor: 'transparent',
        lineWidth: 0,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      
      entryAreaSeries.setData([
        { time: startTime, value: entryHigh },
        { time: endTime, value: entryHigh },
      ]);
      seriesList.push(entryAreaSeries);
    }
    
    // ========================================
    // 2. STOP LOSS (critical boundary)
    // ========================================
    if (stop_loss) {
      priceSeries.createPriceLine({
        price: stop_loss,
        color: EVL_COLORS.stop,
        lineWidth: 3,
        lineStyle: 2, // Dashed — critical but distinct
        axisLabelVisible: true,
        title: 'STOP',
      });
      
      // Risk zone (from entry to stop)
      if (entry_zone && entry_zone.length >= 2) {
        const entryMid = (entry_zone[0] + entry_zone[1]) / 2;
        const riskAreaSeries = chart.addSeries(AreaSeries, {
          topColor: EVL_COLORS.riskZone,
          bottomColor: 'transparent',
          lineColor: 'transparent',
          lineWidth: 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        
        // Risk zone spans from entry to stop
        const riskTop = isShort ? stop_loss : entryMid;
        const riskBottom = isShort ? entryMid : stop_loss;
        
        riskAreaSeries.setData([
          { time: startTime, value: Math.max(riskTop, riskBottom) },
          { time: endTime, value: Math.max(riskTop, riskBottom) },
        ]);
        seriesList.push(riskAreaSeries);
      }
    }
    
    // ========================================
    // 3. TARGET 1 (primary)
    // ========================================
    if (target_1) {
      priceSeries.createPriceLine({
        price: target_1,
        color: EVL_COLORS.tp1,
        lineWidth: 2,
        lineStyle: 0, // Solid — main target
        axisLabelVisible: true,
        title: 'TP1',
      });
      
      // Reward zone (from entry to TP1)
      if (entry_zone && entry_zone.length >= 2) {
        const entryMid = (entry_zone[0] + entry_zone[1]) / 2;
        const rewardAreaSeries = chart.addSeries(AreaSeries, {
          topColor: EVL_COLORS.rewardZone,
          bottomColor: 'transparent',
          lineColor: 'transparent',
          lineWidth: 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        
        const rewardTop = isShort ? entryMid : target_1;
        
        rewardAreaSeries.setData([
          { time: startTime, value: rewardTop },
          { time: endTime, value: rewardTop },
        ]);
        seriesList.push(rewardAreaSeries);
      }
    }
    
    // ========================================
    // 4. TARGET 2 (secondary, optional)
    // ========================================
    if (target_2) {
      priceSeries.createPriceLine({
        price: target_2,
        color: EVL_COLORS.tp2,
        lineWidth: 1,
        lineStyle: 1, // Dotted — less prominent
        axisLabelVisible: true,
        title: 'TP2',
      });
    }
    
    // ========================================
    // 5. R:R BADGE
    // ========================================
    // R:R is displayed via title on TP1 line or via overlay
    // The priceLine title already shows TP1
    // We add R:R info to entry line
    if (rr && entry_zone && entry_zone.length >= 2) {
      const rrText = `R:R ${rr.toFixed(1)}`;
      // Update entry line with R:R
      // Note: This requires modifying the title above
      // For now, R:R is implicit from visual zones
    }
    
  } catch (e) {
    console.warn('[ExecutionVisualLayer] Error rendering:', e);
  }
  
  return seriesList;
}

/**
 * Build execution overlay data from ta_composition + trade_setup
 */
export function buildExecutionOverlay(taComposition, tradeSetup, currentPrice) {
  if (!tradeSetup?.primary?.valid) {
    return null;
  }
  
  const setup = tradeSetup.primary;
  const entryMid = setup.entry_zone 
    ? (setup.entry_zone[0] + setup.entry_zone[1]) / 2 
    : currentPrice;
  
  // Near-price check
  if (Math.abs(currentPrice - entryMid) / currentPrice > 0.05) {
    return null;
  }
  
  return {
    direction: setup.direction,
    entry_zone: setup.entry_zone,
    stop: setup.stop_loss,
    tp1: setup.target_1,
    tp2: setup.target_2,
    rr: setup.rr,
    valid: true,
  };
}

export default { renderExecutionLayer, buildExecutionOverlay, EVL_COLORS };
