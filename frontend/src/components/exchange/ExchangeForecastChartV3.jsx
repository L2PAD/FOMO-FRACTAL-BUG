/**
 * Exchange Forecast Chart V3 — FINAL
 * ====================================
 * 1 DB forecast = 1 autonomous candle.
 *   open = entryPrice of that forecast
 *   close = targetPrice of that forecast
 *
 * NO chaining. NO dailyMove. NO simulation. NO band. NO line-series.
 *
 * Layers:
 *   1. Real candles (green/red)
 *   2. Forecast candles (green/red, autonomous)
 *   3. 7D overlay candles (only in 30D mode, brighter)
 *   4. NOW vertical line
 *   5. Target marker
 */

import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, CrosshairMode, LineSeries, CandlestickSeries, HistogramSeries, AreaSeries, createSeriesMarkers } from "lightweight-charts";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const MAX_VISUAL_MOVE = 0.05; // 5% — clamp candle visual size
const MAX_FORECASTS = 35;     // show all forecast candles (up to 30D)

/**
 * Convert ForecastPoints to CHAINED candles — NORMALIZED.
 * Each point's target = currentPrice * (1 + expectedMovePct/100)
 * This anchors ALL projections to the current market price,
 * eliminating visual "jumps" from old historical entry prices.
 * open(N) = close(N-1) — continuous curve, no gaps.
 */
function pointsToCandles(points, currentPrice, nowSec) {
  if (!points?.length || !currentPrice) return [];
  const sorted = [...points]
    .sort((a, b) => a.targetDateTs - b.targetDateTs)
    .slice(-MAX_FORECASTS);

  const candles = [];
  let prevClose = currentPrice;
  const now = nowSec || Math.floor(Date.now() / 1000);

  for (const p of sorted) {
    const o = Math.round(prevClose * 100) / 100;

    // NORMALIZED: project from currentPrice using model's expected move
    const normalizedTarget = currentPrice * (1 + (p.expectedMovePct || 0) / 100);
    let delta = (normalizedTarget - prevClose) / prevClose;
    if (Math.abs(delta) > MAX_VISUAL_MOVE) {
      delta = Math.sign(delta) * MAX_VISUAL_MOVE;
    }

    const c = Math.round(o * (1 + delta) * 100) / 100;
    const high = Math.round(Math.max(o, c) * 1.006 * 100) / 100;
    const low  = Math.round(Math.min(o, c) * 0.994 * 100) / 100;

    // Gradient opacity: near future brighter, far future more transparent
    const daysAhead = (p.targetDateTs - now) / 86400;
    let opacity;
    if (daysAhead <= 0) opacity = 1;
    else if (daysAhead <= 7) opacity = 0.9;
    else opacity = 0.7;

    const green = `rgba(34, 197, 94, ${opacity})`;
    const red   = `rgba(239, 68, 68, ${opacity})`;
    const clr = c >= o ? green : red;

    candles.push({
      time: p.targetDateTs, open: o, close: c, high, low,
      color: clr, wickColor: clr, borderColor: clr,
    });
    prevClose = c;
  }

  return candles;
}

const chartOptions = {
  layout: {
    background: { type: ColorType.Solid, color: '#ffffff' },
    textColor: '#1f2937',
  },
  grid: {
    vertLines: { color: '#f3f4f6' },
    horzLines: { color: '#f3f4f6' },
  },
  crosshair: {
    mode: CrosshairMode.Normal,
    vertLine: { color: '#9ca3af', width: 1, style: 2 },
    horzLine: { color: '#9ca3af', width: 1, style: 2 },
  },
  rightPriceScale: {
    borderColor: '#e5e7eb',
    scaleMargins: { top: 0.1, bottom: 0.2 },
  },
  timeScale: {
    borderColor: '#e5e7eb',
    timeVisible: true,
    secondsVisible: false,
  },
  localization: { locale: 'en-US' },
};

export default function ExchangeForecastChartV3({ symbol = 'BTC', horizon = '7D', viewMode = 'candle' }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const [data, setData] = useState(null);
  const [evolution, setEvolution] = useState(null);
  const [showEvolution, setShowEvolution] = useState(true);
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const hDays = horizon === '1D' ? 1 : horizon === '30D' ? 30 : 7;

    // Fetch chart data + evolution + prediction in parallel
    Promise.all([
      fetch(`${API_URL}/api/market/chart/exchange-v3?asset=${symbol}&horizon=${horizon}`)
        .then(r => r.json()),
      fetch(`${API_URL}/api/market/chart/forecast-evolution?asset=${symbol}&horizon=${hDays}`)
        .then(r => r.json())
        .catch(() => null), // evolution is optional, don't block chart
      fetch(`${API_URL}/api/forecast/prediction/${symbol}`)
        .then(r => r.json())
        .catch(() => null), // prediction is optional
    ])
      .then(([chartData, evoData, predData]) => {
        if (!chartData.ok) throw new Error(chartData.error || 'Server error');
        setData(chartData);
        if (evoData?.ok) setEvolution(evoData);
        if (predData?.ok) setPrediction(predData);
        setLoading(false);
      })
      .catch(err => { setError(err.message); setLoading(false); });
  }, [symbol, horizon]);

  useEffect(() => {
    if (!containerRef.current || loading || !data) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }
    containerRef.current.querySelectorAll('[data-overlay]').forEach(el => el.remove());

    const chart = createChart(containerRef.current, {
      ...chartOptions,
      width: containerRef.current.clientWidth,
      height: 420,
    });
    chartRef.current = chart;
    const container = containerRef.current;

    const { realCandles, forecastPoints, overlay7DPoints, target } = data;
    const nowSec = data.nowTs || Math.floor(Date.now() / 1000);

    // Layer 1: Real candles or line
    let realSeries;
    if (viewMode === 'line') {
      realSeries = chart.addSeries(LineSeries, {
        color: '#2563eb',
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
      });
      if (realCandles?.length) {
        realSeries.setData(realCandles.map(c => ({ time: c.time, value: c.close })));
      }
    } else {
      realSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#16a34a',
        downColor: '#dc2626',
        borderVisible: false,
        wickUpColor: '#16a34a',
        wickDownColor: '#dc2626',
      });
      if (realCandles?.length) realSeries.setData(realCandles);
    }

    // Get current price from last real candle (for chaining start)
    const lastRealClose = realCandles?.length ? realCandles[realCandles.length - 1].close : null;

    // Layer 2: Forecast
    if (viewMode === 'line') {
      // Line mode: use normalized forecast points (currentPrice × expectedMovePct)
      const allPoints = [
        ...(overlay7DPoints || []),
        ...(forecastPoints || []),
      ]
        .sort((a, b) => a.targetDateTs - b.targetDateTs)
        .filter((p, i, arr) => i === 0 || p.targetDateTs !== arr[i - 1].targetDateTs);

      if (allPoints.length && lastRealClose) {
        const forecastSeries = chart.addSeries(LineSeries, {
          color: '#000000',
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: true,
          crosshairMarkerVisible: true,
        });

        const lineData = [];
        // Connect from current price ("now") to first forecast
        if (realCandles?.length) {
          lineData.push({ time: realCandles[realCandles.length - 1].time, value: lastRealClose });
        }
        for (const p of allPoints) {
          const normalizedTarget = lastRealClose * (1 + (p.expectedMovePct || 0) / 100);
          lineData.push({ time: p.targetDateTs, value: normalizedTarget });
        }
        forecastSeries.setData(lineData);
      }
    } else {
      // Candle mode: existing logic with pointsToCandles
      const forecastCandles = pointsToCandles(forecastPoints, lastRealClose, nowSec);
      if (forecastCandles.length) {
        const forecastSeries = chart.addSeries(CandlestickSeries, {
          upColor: 'rgba(34, 197, 94, 0.6)',
          downColor: 'rgba(239, 68, 68, 0.6)',
          borderVisible: false,
          wickUpColor: 'rgba(34, 197, 94, 0.6)',
          wickDownColor: 'rgba(239, 68, 68, 0.6)',
        });
        forecastSeries.setData(forecastCandles);
      }

      // 7D overlay DISABLED — 30D now has full 30-day cycle, no gaps to fill
      // overlay7DPoints would create conflicting candles on the same dates
    }

    // Layer 5: Target overlays REMOVED — user requested clean chart without forecast lines/bands
    // The forecast candles (Layer 2) already show projected direction visually.

    // Layer 7: Story Overlay (1 line on chart, right edge)
    if (prediction?.horizons) {
      const h7d = prediction.horizons['7D'];
      const h30d = prediction.horizons['30D'];
      if (h7d || h30d) {
        const shortMove = h7d?.expected_move_pct || 0;
        const longMove = h30d?.expected_move_pct || 0;
        const sUp = shortMove > 0.1, sDown = shortMove < -0.1;
        const lUp = longMove > 0.1, lDown = longMove < -0.1;

        let story = '';
        let storyColor = '#ca8a04'; // yellow default (mixed)
        if (sUp && lDown) { story = 'Bounce inside downtrend'; storyColor = '#ca8a04'; }
        else if (sDown && lUp) { story = 'Pullback in uptrend'; storyColor = '#ca8a04'; }
        else if (sUp && lUp) { story = 'Trend continuation (bullish)'; storyColor = '#16a34a'; }
        else if (sDown && lDown) { story = 'Trend continuation (bearish)'; storyColor = '#dc2626'; }
        else { story = 'Consolidation'; storyColor = '#6b7280'; }

        const storyEl = document.createElement('div');
        storyEl.setAttribute('data-overlay', 'story');
        storyEl.setAttribute('data-testid', 'chart-story-overlay');
        Object.assign(storyEl.style, {
          position: 'absolute', top: '8px', right: '80px',
          fontSize: '11px', fontWeight: '600', letterSpacing: '0.02em',
          color: storyColor, pointerEvents: 'none', zIndex: '12',
          background: 'rgba(255,255,255,0.85)', padding: '3px 8px',
          borderRadius: '4px', border: `1px solid ${storyColor}33`,
        });
        storyEl.textContent = `→ ${story}`;
        container.appendChild(storyEl);
      }
    }

    // Layer 6: Forecast Evolution Line (purple) — AI opinion change over time
    // Controlled by showEvolution toggle. Last 60 runs only.
    // Includes outlier filtering: reject points that deviate > 8% from rolling median.
    if (showEvolution && evolution?.points?.length) {
      const MAX_EVO_POINTS = 60;
      const evoSeries = chart.addSeries(LineSeries, {
        color: 'rgba(124, 58, 237, 0.5)',
        lineWidth: 1,
        lineStyle: 0,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 3,
        priceLineVisible: false,
        lastValueVisible: false,
        title: 'AI Evolution',
      });
      let evoData = evolution.points
        .map(p => ({ time: p.date, value: p.target }))
        .filter(p => p.time > 0 && p.value > 0)
        .slice(-MAX_EVO_POINTS);

      // Outlier filter: remove points that jump >8% from their neighbors' median.
      // Typical daily model drift is 1-3%; anything beyond 8% is noise/glitch.
      if (evoData.length > 3) {
        const filtered = [evoData[0]];
        for (let i = 1; i < evoData.length - 1; i++) {
          const prev = filtered[filtered.length - 1].value; // use last accepted point
          const next = evoData[i + 1].value;
          const neighborMed = (prev + next) / 2;
          const deviation = Math.abs(evoData[i].value - neighborMed) / neighborMed;
          if (deviation < 0.08) {
            filtered.push(evoData[i]);
          }
        }
        filtered.push(evoData[evoData.length - 1]);
        evoData = filtered;
      }

      if (evoData.length) {
        evoSeries.setData(evoData);

        const markers = evoData.map(p => ({
          time: p.time,
          position: 'inBar',
          shape: 'circle',
          color: 'rgba(124, 58, 237, 0.6)',
          size: 0.5,
        }));
        createSeriesMarkers(evoSeries, markers);
      }
    }

    chart.timeScale().fitContent();

    // Layer 4: NOW vertical (container already declared above)
    const nowLine = document.createElement('div');
    nowLine.setAttribute('data-overlay', 'now-line');
    Object.assign(nowLine.style, {
      position: 'absolute', top: '0', bottom: '30px', width: '2px',
      background: '#7c3aed', opacity: '0.6', pointerEvents: 'none', zIndex: '10',
      display: 'none',
    });
    container.appendChild(nowLine);

    const nowLabel = document.createElement('div');
    nowLabel.setAttribute('data-overlay', 'now-label');
    Object.assign(nowLabel.style, {
      position: 'absolute', bottom: '32px', fontSize: '9px', fontWeight: '700',
      color: '#7c3aed', pointerEvents: 'none', zIndex: '11', display: 'none',
    });
    nowLabel.textContent = 'NOW';
    container.appendChild(nowLabel);

    let rafId;
    const syncNow = () => {
      const x = chart.timeScale().timeToCoordinate(nowSec);
      if (x !== null && x >= 0) {
        nowLine.style.left = `${x}px`;
        nowLine.style.display = '';
        nowLabel.style.left = `${x - 10}px`;
        nowLabel.style.display = '';
      } else {
        nowLine.style.display = 'none';
        nowLabel.style.display = 'none';
      }
      rafId = requestAnimationFrame(syncNow);
    };
    rafId = requestAnimationFrame(syncNow);

    const ro = new ResizeObserver(entries => {
      if (entries.length > 0) chart.applyOptions({ width: entries[0].contentRect.width });
    });
    ro.observe(container);

    return () => {
      if (rafId) cancelAnimationFrame(rafId);
      ro.disconnect();
      container.querySelectorAll('[data-overlay]').forEach(el => el.remove());
      chart.remove();
      chartRef.current = null;
    };
  }, [data, loading, evolution, showEvolution, viewMode, prediction]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 h-[420px] flex items-center justify-center" data-testid="chart-v3-loading">
        <div className="w-8 h-8 border-3 border-gray-200 border-t-blue-600 rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 h-[420px] flex flex-col items-center justify-center" data-testid="chart-v3-error">
        <p className="text-red-600 font-medium">Error loading chart</p>
        <p className="text-sm text-gray-500 mt-1">{error}</p>
      </div>
    );
  }

  const direction = data?.direction || 'NEUTRAL';
  const dirColor = direction === 'LONG' ? '#16a34a' : direction === 'SHORT' ? '#dc2626' : '#6b7280';
  const confidence = Math.round((data?.confidence || 0) * 100);
  const stability = data?.meta?.stability || 'unknown';
  const stabilityColor = stability === 'stable' ? '#16a34a' : stability === 'moderate' ? '#ca8a04' : stability === 'unstable' ? '#dc2626' : '#9ca3af';
  const signalColor = confidence >= 70 ? '#16a34a' : confidence >= 50 ? '#16a34a' : confidence >= 30 ? '#ca8a04' : '#9ca3af';
  const hDays = data?.horizonDays || 0;
  const numPoints = data?.forecastPoints?.length || 0;
  const has7DOverlay = data?.overlay7DPoints?.length > 0;

  // Drift from evolution endpoint
  const driftStatus = evolution?.drift?.status || null;
  const driftColor = driftStatus === 'stable' ? '#16a34a' : driftStatus === 'moderate' ? '#ca8a04' : driftStatus === 'unstable' ? '#dc2626' : '#9ca3af';
  const trend = evolution?.trend || null;
  const trendIcon = trend?.direction === 'bullish' ? '\u2191' : trend?.direction === 'bearish' ? '\u2193' : '\u2194';
  const trendColor = trend?.direction === 'bullish' ? '#16a34a' : trend?.direction === 'bearish' ? '#dc2626' : '#6b7280';

  // Decision context data for footer
  const predH30d = prediction?.horizons?.['30D'];
  const predH7d = prediction?.horizons?.['7D'];
  const dominant30 = predH30d?.dominant;
  const dominantProb = dominant30 ? predH30d?.probabilities?.[dominant30] : null;
  const shortMv = predH7d?.expected_move_pct || 0;
  const longMv = predH30d?.expected_move_pct || 0;
  const shortD = shortMv > 0.1 ? 'bullish' : shortMv < -0.1 ? 'bearish' : 'neutral';
  const longD = longMv > 0.1 ? 'bullish' : longMv < -0.1 ? 'bearish' : 'neutral';
  const isDivergent = (shortD === 'bullish' && longD === 'bearish') || (shortD === 'bearish' && longD === 'bullish');
  const isAligned = shortD === longD && shortD !== 'neutral';
  const agreement = prediction?.summary?.horizon_agreement;

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid="chart-v3-container">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-gray-600" data-testid="chart-v3-title">Exchange</span>
          {direction === 'LONG' || direction === 'BULLISH'
            ? <TrendingUp className="w-4 h-4 text-emerald-600" />
            : direction === 'SHORT' || direction === 'BEARISH'
              ? <TrendingDown className="w-4 h-4 text-red-600" />
              : <Minus className="w-4 h-4 text-gray-400" />
          }
          <span
            className={`text-sm font-bold ${
              direction === 'LONG' || direction === 'BULLISH'
                ? 'text-emerald-600'
                : direction === 'SHORT' || direction === 'BEARISH'
                  ? 'text-red-600'
                  : 'text-gray-500'
            }`}
            data-testid="chart-v3-direction"
          >
            {direction === 'LONG' || direction === 'BULLISH' ? 'Bullish'
              : direction === 'SHORT' || direction === 'BEARISH' ? 'Bearish'
              : 'HOLD'}
          </span>
          <span className="text-sm font-medium text-gray-500" data-testid="chart-v3-confidence">{confidence}%</span>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <label
            className="flex items-center gap-1.5 cursor-pointer select-none"
            data-testid="chart-v3-evo-toggle"
          >
            <input
              type="checkbox"
              checked={showEvolution}
              onChange={e => setShowEvolution(e.target.checked)}
              className="w-3 h-3 accent-purple-600"
            />
            <span className="text-[10px] text-purple-600 font-medium">AI Evolution</span>
          </label>
        </div>
      </div>
      <div ref={containerRef} style={{ height: 420, position: 'relative' }} data-testid="chart-v3-canvas" />

      {/* Decision context footer */}
      {prediction?.horizons && (
        <div data-testid="chart-decision-footer" className="px-4 py-2.5 border-t border-gray-100 flex items-center gap-5 text-[11px]">
          {/* Probability hint */}
          {dominant30 && dominantProb != null && (
            <span data-testid="chart-probability-hint" className="text-gray-500">
              <span className="font-medium">30D:</span>{' '}
              <span className={`font-semibold ${
                dominant30 === 'bullish' ? 'text-emerald-600' : dominant30 === 'bearish' ? 'text-red-600' : 'text-gray-600'
              }`}>
                {dominant30 === 'bullish' ? '↑' : dominant30 === 'bearish' ? '↓' : '→'}{' '}
                {dominant30} ({Math.round(dominantProb * 100)}%)
              </span>
            </span>
          )}

          {/* Divergence / Alignment */}
          {(isDivergent || isAligned) && (
            <span data-testid="chart-divergence-hint" className={`font-semibold ${
              isDivergent ? 'text-amber-600' : 'text-emerald-600'
            }`}>
              {isDivergent ? '⚠️ Short-term vs Long-term divergence' : '✓ Horizons aligned'}
            </span>
          )}

          {/* Agreement score */}
          {agreement != null && (
            <span className="text-gray-400 ml-auto">
              Agreement: <span className="font-medium text-gray-600">{Math.round(agreement * 100)}%</span>
            </span>
          )}
        </div>
      )}
    </div>
  );
}
