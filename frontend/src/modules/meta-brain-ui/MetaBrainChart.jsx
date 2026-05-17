/**
 * MetaBrainChart — Rolling Forecast Curve
 *
 * Visual pattern:
 * - Real BTC candles (CandlestickSeries) + Volume (HistogramSeries)
 * - History line: black line following candle closes up to NOW
 * - Forecast curve: colored line (green/red/gray by verdict) from NOW forward
 *   Built from REAL forecast points stored in meta_brain_forecasts,
 *   NOT from artificial interpolation.
 * - Vertical NOW line separating history from forecast
 * - Markers: 1D, 7D, 30D labeled points on the forecast curve
 *
 * Data sources:
 * - Candles: /api/ui/candles
 * - Forecast curve: /api/meta-brain-v2/forecast-curve
 */
import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { createChart, CrosshairMode, CandlestickSeries, HistogramSeries, LineSeries, createSeriesMarkers } from 'lightweight-charts';
import { RefreshCw, TrendingUp, TrendingDown, Minus } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ═══════════════════════════════════════════════════════════════
// MONOTONE CUBIC INTERPOLATION (Fritsch-Carlson)
// Generates smooth daily points from sparse forecast data
// ═══════════════════════════════════════════════════════════════

function daysBetween(a, b) {
  const msA = Date.parse(a + 'T00:00:00Z');
  const msB = Date.parse(b + 'T00:00:00Z');
  return Math.round((msB - msA) / 86400000);
}

function addDays(dateStr, days) {
  const ms = Date.parse(dateStr + 'T00:00:00Z') + days * 86400000;
  const d = new Date(ms);
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** Deduplicate + sort time series data (safety net for lightweight-charts) */
function dedupSorted(arr) {
  if (arr.length <= 1) return arr;
  const sorted = [...arr].sort((a, b) => (a.time || a.t || '').localeCompare(b.time || b.t || ''));
  return sorted.filter((p, i) => {
    const key = p.time || p.t;
    const prev = i > 0 ? (sorted[i - 1].time || sorted[i - 1].t) : null;
    return key !== prev;
  });
}

function cubicSmooth(points) {
  if (points.length < 2) return points;
  if (points.length === 2) {
    // Linear fill between 2 points
    const result = [];
    const totalDays = daysBetween(points[0].t, points[1].t);
    for (let d = 0; d <= totalDays; d++) {
      const progress = d / totalDays;
      result.push({
        t: addDays(points[0].t, d),
        v: Math.round((points[0].v + (points[1].v - points[0].v) * progress) * 100) / 100,
      });
    }
    return result;
  }

  // Convert dates to numeric x (days from first point)
  const x = points.map(p => daysBetween(points[0].t, p.t));
  const y = points.map(p => p.v);
  const n = x.length;

  // Compute slopes
  const delta = [];
  for (let i = 0; i < n - 1; i++) {
    delta.push((y[i + 1] - y[i]) / (x[i + 1] - x[i]));
  }

  // Monotone tangents (Fritsch-Carlson)
  const m = new Array(n);
  m[0] = delta[0];
  m[n - 1] = delta[n - 2];
  for (let i = 1; i < n - 1; i++) {
    if (delta[i - 1] * delta[i] <= 0) {
      m[i] = 0;
    } else {
      m[i] = (delta[i - 1] + delta[i]) / 2;
    }
  }

  // Generate daily points
  const result = [];
  const totalDays = x[n - 1];
  for (let d = 0; d <= totalDays; d++) {
    // Find segment
    let seg = 0;
    for (let i = 0; i < n - 1; i++) {
      if (d >= x[i] && d <= x[i + 1]) { seg = i; break; }
    }

    const h = x[seg + 1] - x[seg];
    if (h === 0) {
      result.push({ t: addDays(points[0].t, d), v: y[seg] });
      continue;
    }
    const t = (d - x[seg]) / h;
    const t2 = t * t;
    const t3 = t2 * t;

    // Hermite basis
    const h00 = 2 * t3 - 3 * t2 + 1;
    const h10 = t3 - 2 * t2 + t;
    const h01 = -2 * t3 + 3 * t2;
    const h11 = t3 - t2;

    const val = h00 * y[seg] + h10 * h * m[seg] + h01 * y[seg + 1] + h11 * h * m[seg + 1];
    result.push({
      t: addDays(points[0].t, d),
      v: Math.round(val * 100) / 100,
    });
  }

  // Deduplicate output (safety net for timezone edge cases)
  const seen = new Set();
  return result.filter(p => {
    if (seen.has(p.t)) return false;
    seen.add(p.t);
    return true;
  });
}

// ═══════════════════════════════════════════════════════════════
// VERDICT COLORS
// ═══════════════════════════════════════════════════════════════

const VERDICT_COLORS = {
  LONG: '#16a34a',
  SHORT: '#dc2626',
  NEUTRAL: '#6b7280',
};

// ═══════════════════════════════════════════════════════════════
// CHART COMPONENT
// ═══════════════════════════════════════════════════════════════

export default function MetaBrainChart({
  asset = 'BTC',
  horizonDays = 7,
  viewMode = 'candle',
  onDataLoad = null,
}) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const closeLineSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const historyLineRef = useRef(null);
  const forecastLineRef = useRef(null);

  const forecastMarkersRef = useRef(null);
  const nowLineRef = useRef(null);
  const arrowRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hoverData, setHoverData] = useState(null);
  const [forecastInfo, setForecastInfo] = useState(null);

  // Fetch candles
  const fetchCandles = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/ui/candles?asset=${asset}&years=2`);
      const data = await res.json();
      if (data.ok && data.candles) {
        return data.candles
          .map(c => {
            let time = c.t;
            if (time && time.includes('T')) time = time.split('T')[0];
            return { time, open: c.o, high: c.h, low: c.l, close: c.c, volume: c.v || 0 };
          })
          .filter(c => c.time)
          .sort((a, b) => a.time.localeCompare(b.time));
      }
      return [];
    } catch (e) {
      console.warn('[MetaBrainChart] candles unavailable (graceful):', e?.message || e);
      return [];
    }
  }, [asset]);

  // Fetch forecast curve — passes horizonDays to get only relevant points
  const fetchForecastCurve = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/meta-brain-v2/forecast-curve?asset=${asset}&horizonDays=${horizonDays}`);
      const data = await res.json();
      if (data.ok) return data;
      return null;
    } catch (e) {
      console.warn('[MetaBrainChart] forecast-curve unavailable (graceful):', e?.message || e);
      return null;
    }
  }, [asset, horizonDays]);

  // Also trigger a /forecast call to ensure a snapshot is saved
  const triggerForecast = useCallback(async () => {
    try {
      await fetch(`${API_URL}/api/meta-brain-v2/forecast?asset=${asset}&horizonDays=${horizonDays}`);
    } catch {}
  }, [asset, horizonDays]);

  // Init chart (once)
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      height: containerRef.current.clientHeight || 520,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333333',
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { labelVisible: true },
        horzLine: { labelVisible: true },
      },
      rightPriceScale: {
        borderColor: '#e5e5e5',
        scaleMargins: { top: 0.05, bottom: 0.2 },
        autoScale: true,
      },
      timeScale: {
        borderColor: '#e5e5e5',
        rightOffset: 12,
        fixLeftEdge: true,
        timeVisible: false,
        secondsVisible: false,
      },
      localization: { locale: 'en-US', dateFormat: 'yyyy-MM-dd' },
      handleScale: { axisPressedMouseMove: true },
      handleScroll: { pressedMouseMove: true },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#16a34a',
      downColor: '#dc2626',
      borderUpColor: '#16a34a',
      borderDownColor: '#dc2626',
      wickUpColor: '#16a34a',
      wickDownColor: '#dc2626',
    });

    // Close-price line (used when viewMode='line')
    const closeLineSeries = chart.addSeries(LineSeries, {
      color: '#2563eb',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      visible: false,
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: '',
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    // History line (black — follows candle closes in the past)
    const historyLine = chart.addSeries(LineSeries, {
      color: '#111827',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
    });

    // Forecast line (colored by verdict — future projection)
    const forecastLine = chart.addSeries(LineSeries, {
      color: '#6b7280',
      lineWidth: 2,
      lineStyle: 0,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
    });

    chart.subscribeCrosshairMove(param => {
      if (!param || !param.time) { setHoverData(null); return; }
      const candleData = param.seriesData.get(candleSeries);
      const histData = param.seriesData.get(historyLine);
      const fcData = param.seriesData.get(forecastLine);
      setHoverData({
        time: param.time,
        candle: candleData,
        prediction: fcData?.value ?? histData?.value,
      });
    });

    const ro = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });
    ro.observe(containerRef.current);

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    closeLineSeriesRef.current = closeLineSeries;
    volumeSeriesRef.current = volumeSeries;
    historyLineRef.current = historyLine;
    forecastLineRef.current = forecastLine;

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  // Toggle candle/line view mode
  useEffect(() => {
    if (!candleSeriesRef.current || !closeLineSeriesRef.current) return;
    const isLine = viewMode === 'line';
    candleSeriesRef.current.applyOptions({ visible: !isLine });
    closeLineSeriesRef.current.applyOptions({ visible: isLine });
    // Hide history line when in line mode (closeLine replaces it)
    if (historyLineRef.current) {
      historyLineRef.current.applyOptions({ visible: !isLine });
    }
  }, [viewMode]);


  // Load data when asset/horizon changes
  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      if (!chartRef.current || !candleSeriesRef.current) return;
      setLoading(true);
      setError(null);

      try {
        // Trigger forecast in background (save snapshot) — don't block chart rendering
        triggerForecast();

        const [candles, curveData] = await Promise.all([fetchCandles(), fetchForecastCurve()]);
        if (cancelled) return;

        if (candles.length === 0) {
          setError('No candle data available');
          setLoading(false);
          return;
        }

        const lastCandle = candles[candles.length - 1];
        const nowDate = lastCandle.time;
        const nowPrice = lastCandle.close;

        // 1. Set candles + future whitespace (deduplicated)
        // Whitespace entries (time-only, no OHLC) extend the time axis into the future
        // so the chart creates proper calendar-spaced bar slots for forecast dates.
        // This is NOT mock data — just empty time slots that real candles will replace.
        const candleData = dedupSorted(candles.map(c => ({
          time: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
        })));
        const futureWhitespace = [];
        if (horizonDays > 1) {
          for (let d = 1; d <= horizonDays + 5; d++) {
            futureWhitespace.push({ time: addDays(nowDate, d) });
          }
        }
        candleSeriesRef.current.setData([...candleData, ...futureWhitespace]);

        // 1b. Set close-price line (for line viewMode)
        const closeLineData = dedupSorted(candles.map(c => ({ time: c.time, value: c.close })));
        closeLineSeriesRef.current.setData([...closeLineData, ...futureWhitespace]);

        // Apply current viewMode visibility
        const isLine = viewMode === 'line';
        candleSeriesRef.current.applyOptions({ visible: !isLine });
        closeLineSeriesRef.current.applyOptions({ visible: isLine });
        if (historyLineRef.current) historyLineRef.current.applyOptions({ visible: !isLine });

        // 2. Set volume (deduplicated)
        volumeSeriesRef.current.setData(
          dedupSorted(candles.map(c => ({
            time: c.time,
            value: c.volume || 0,
            color: c.close >= c.open ? 'rgba(22,163,74,0.2)' : 'rgba(220,38,38,0.2)',
          })))
        );

        // 3. Build history line (candle closes up to NOW, deduplicated)
        const historyData = dedupSorted(candles.map(c => ({ time: c.time, value: c.close })));
        historyLineRef.current.setData(historyData);

        // 4. Build forecast based on horizon type
        const verdict = curveData?.verdict || 'NEUTRAL';
        const forecastColor = VERDICT_COLORS[verdict] || VERDICT_COLORS.NEUTRAL;
        const forecastReturn = curveData?.forecastReturn || 0;
        forecastLineRef.current.applyOptions({ color: forecastColor });

        if (horizonDays <= 1) {
          // ─── 1D HORIZON: NO FORECAST LINE — just arrow + percentage ───
          forecastLineRef.current.setData([]);
          if (forecastMarkersRef.current) {
            forecastMarkersRef.current.setMarkers([]);
          }
          setForecastInfo({
            verdict,
            metaConfidence: curveData?.metaConfidence,
            regime: curveData?.regime,
            priceNow: nowPrice,
            forecastReturn,
            is1D: true,
            latestForecast: curveData?.latestForecast,
            snapshotCount: curveData?.snapshotCount || 0,
          });
        } else if (curveData?.curve?.length > 0) {
          // ─── 7D / 30D HORIZON: Real forecast line ───
          const futurePoints = curveData.curve.filter(p => p.t >= nowDate);

          // Ensure anchor at nowDate/nowPrice
          if (futurePoints.length === 0 || futurePoints[0].t !== nowDate) {
            futurePoints.unshift({ t: nowDate, v: nowPrice });
          } else {
            futurePoints[0].v = nowPrice;
          }

          // ONLY real data points — no interpolation, no mock data
          const forecastData = dedupSorted(futurePoints.map(p => ({ time: p.t, value: p.v })));
          forecastLineRef.current.setData(forecastData);

          // Add markers for target points — only latest 7D and latest 30D
          if (curveData.markers?.length > 0) {
            const futureMarkers = curveData.markers.filter(m => m.t > nowDate);
            // Keep only the latest marker per label (7D, 30D)
            const latestByLabel = {};
            for (const m of futureMarkers) {
              if (!latestByLabel[m.label] || m.t > latestByLabel[m.label].t) {
                latestByLabel[m.label] = m;
              }
            }
            const chartMarkers = Object.values(latestByLabel)
              .sort((a, b) => a.t.localeCompare(b.t))
              .map(m => ({
                time: m.t,
                position: 'inBar',
                color: forecastColor,
                shape: 'circle',
                size: 0.5,
                text: m.label,
              }));
            if (chartMarkers.length > 0) {
              if (forecastMarkersRef.current) {
                forecastMarkersRef.current.setMarkers(chartMarkers);
              } else {
                forecastMarkersRef.current = createSeriesMarkers(forecastLineRef.current, chartMarkers);
              }
            }
          }

          setForecastInfo({
            verdict,
            metaConfidence: curveData?.metaConfidence,
            regime: curveData?.regime,
            priceNow: nowPrice,
            forecastReturn: 0,
            is1D: false,
            latestForecast: curveData?.latestForecast,
            snapshotCount: curveData?.snapshotCount || 0,
          });

          if (onDataLoad) onDataLoad(curveData);
        } else if (verdict === 'NEUTRAL' && Math.abs(forecastReturn) < 0.01) {
          // NEUTRAL with negligible move and NO curve data: arrow only
          forecastLineRef.current.setData([]);
          if (forecastMarkersRef.current) {
            forecastMarkersRef.current.setMarkers([]);
          }
          setForecastInfo({
            verdict,
            metaConfidence: curveData?.metaConfidence,
            regime: curveData?.regime,
            priceNow: nowPrice,
            forecastReturn,
            is1D: true,
            latestForecast: curveData?.latestForecast,
            snapshotCount: curveData?.snapshotCount || 0,
          });
        } else {
          forecastLineRef.current.setData([]);
          setForecastInfo(null);
        }

        // 5. Set visible range — forecast points are now at correct calendar positions
        // because whitespace bars create daily bar slots on the time axis
        const totalBars = candleData.length + futureWhitespace.length;
        // 1D: same scale as 7D (no zoom-in), show plenty of history
        const lookbackBars = horizonDays <= 7 ? 65 : 65;
        const bufferBars = horizonDays <= 1 ? 8 : 5;

        // rightOffset: small whitespace after last bar
        chartRef.current.timeScale().applyOptions({ rightOffset: bufferBars });

        // Visible range: [nowBar - lookback ... lastBar + buffer]
        const nowBarIdx = candleData.length - 1;
        const fromBar = nowBarIdx - lookbackBars;
        const toBar = horizonDays <= 1 
          ? nowBarIdx + 10  // 1D: add space after last candle for arrow
          : totalBars - 1 + bufferBars;

        setTimeout(() => {
          if (!chartRef.current) return;
          try {
            chartRef.current.timeScale().setVisibleLogicalRange({
              from: fromBar,
              to: toBar,
            });
          } catch (e) {
            console.warn('[MetaBrainChart] setVisibleLogicalRange error:', e);
          }
        }, 100);

        // 6. NOW vertical line + 1D arrow — positioned using timeToCoordinate + priceToCoordinate
        const updateNowLine = () => {
          if (!chartRef.current) return;
          const coord = chartRef.current.timeScale().timeToCoordinate(nowDate);
          if (coord !== null && coord >= 0) {
            // Position NOW line
            if (nowLineRef.current) {
              nowLineRef.current.style.left = `${coord}px`;
              nowLineRef.current.style.display = 'block';
            }
            // Position 1D arrow at the price level of last candle
            if (arrowRef.current && candleSeriesRef.current) {
              const yCoord = candleSeriesRef.current.priceToCoordinate(nowPrice);
              if (yCoord !== null && yCoord >= 0) {
                arrowRef.current.style.left = `${coord + 12}px`;
                arrowRef.current.style.top = `${yCoord - 10}px`;
                arrowRef.current.style.display = 'flex';
              } else {
                arrowRef.current.style.display = 'none';
              }
            }
          } else {
            if (nowLineRef.current) nowLineRef.current.style.display = 'none';
            if (arrowRef.current) arrowRef.current.style.display = 'none';
          }
        };
        updateNowLine();
        chartRef.current.timeScale().subscribeVisibleLogicalRangeChange(updateNowLine);
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadData();
    return () => { cancelled = true; };
  }, [asset, horizonDays, fetchCandles, fetchForecastCurve, triggerForecast, onDataLoad]);

  const verdictColor = useMemo(() => {
    if (!forecastInfo) return 'text-gray-500';
    if (forecastInfo.verdict === 'LONG') return 'text-emerald-600';
    if (forecastInfo.verdict === 'SHORT') return 'text-red-600';
    return 'text-gray-600';
  }, [forecastInfo]);

  const VerdictIcon = useMemo(() => {
    if (!forecastInfo) return Minus;
    if (forecastInfo.verdict === 'LONG') return TrendingUp;
    if (forecastInfo.verdict === 'SHORT') return TrendingDown;
    return Minus;
  }, [forecastInfo]);

  return (
    <div className="relative w-full" data-testid="meta-brain-chart">
      {/* Chart Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-gray-600" data-testid="meta-brain-title">Meta Brain</span>
          {forecastInfo && (
            <>
              <VerdictIcon className={`w-4 h-4 ${verdictColor}`} />
              <span
                className={`text-sm font-bold ${verdictColor}`}
                data-testid="meta-brain-stance"
              >
                {forecastInfo.verdict === 'LONG' || forecastInfo.verdict === 'BULLISH' ? 'Bullish'
                  : forecastInfo.verdict === 'SHORT' || forecastInfo.verdict === 'BEARISH' ? 'Bearish'
                  : 'HOLD'}
              </span>
              <span className="text-sm font-medium text-gray-500" data-testid="meta-brain-confidence">
                {Math.round((forecastInfo.metaConfidence || 0) * 100)}%
              </span>
            </>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10 rounded-2xl">
          <p className="text-red-600">{error}</p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/60 z-10 rounded-2xl">
          <RefreshCw className="w-8 h-8 text-gray-400 animate-spin" />
        </div>
      )}

      {/* Hover Tooltip */}
      {hoverData?.candle && (
        <div
          className="absolute top-12 left-4 bg-white border border-gray-100 rounded-xl shadow-lg p-3 z-20 min-w-[160px]"
          style={{ pointerEvents: 'none' }}
        >
          <div className="text-xs text-gray-500 mb-2">
            {typeof hoverData.time === 'string' ? hoverData.time : new Date(hoverData.time * 1000).toISOString().split('T')[0]}
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <span className="text-gray-400">O</span>
            <span className="font-medium text-right">{hoverData.candle.open?.toLocaleString('en-US')}</span>
            <span className="text-gray-400">H</span>
            <span className="font-medium text-right">{hoverData.candle.high?.toLocaleString('en-US')}</span>
            <span className="text-gray-400">L</span>
            <span className="font-medium text-right">{hoverData.candle.low?.toLocaleString('en-US')}</span>
            <span className="text-gray-400">C</span>
            <span className="font-medium text-right">{hoverData.candle.close?.toLocaleString('en-US')}</span>
          </div>
          {hoverData.prediction != null && (
            <div className="mt-2 pt-2 border-t border-gray-100">
              <span className="text-gray-400 text-xs">Forecast: </span>
              <span className="font-medium text-xs">{hoverData.prediction.toLocaleString('en-US')}</span>
            </div>
          )}
        </div>
      )}

      {/* Chart Canvas + NOW line */}
      <div className="relative">
        <div
          ref={containerRef}
          className="w-full rounded-2xl border border-gray-100 overflow-hidden"
          style={{ height: '65vh', minHeight: '400px' }}
          data-testid="chart-canvas"
        />
        {/* NOW vertical line overlay — stops above volume zone + time axis */}
        <div
          ref={nowLineRef}
          className="absolute pointer-events-none"
          style={{
            display: 'none',
            top: 0,
            width: '1px',
            height: '78%',
            background: 'rgba(107, 114, 128, 0.3)',
            borderLeft: '1px dashed rgba(107, 114, 128, 0.5)',
            zIndex: 5,
          }}
        >
          <div className="absolute -top-0 left-1 bg-gray-500 text-white text-[9px] px-1.5 py-0.5 rounded font-medium">
            NOW
          </div>
        </div>

        {/* 1D ARROW — compact, pinned to chart at price level */}
        {forecastInfo?.is1D && (
          <div
            ref={arrowRef}
            className="absolute pointer-events-none items-center gap-0.5"
            style={{
              display: 'none',
              zIndex: 6,
              whiteSpace: 'nowrap',
            }}
          >
            <span className={`text-base font-bold ${
              forecastInfo.verdict === 'LONG' ? 'text-emerald-600' :
              forecastInfo.verdict === 'SHORT' ? 'text-red-500' :
              'text-gray-500'
            }`}>
              {forecastInfo.verdict === 'LONG' ? '↗' :
               forecastInfo.verdict === 'SHORT' ? '↘' : '→'}{' '}
              {forecastInfo.forecastReturn >= 0 ? '+' : ''}{(forecastInfo.forecastReturn * 100).toFixed(1)}%
            </span>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 mt-3 text-xs text-gray-500">
        <div className="flex items-center gap-2">
          <div className="w-4 h-0.5 bg-gray-900"></div>
          <span>Price History</span>
        </div>
        {!forecastInfo?.is1D && (
          <>
            <div className="flex items-center gap-2">
              <div
                className="w-4 h-0.5"
                style={{ backgroundColor: forecastInfo ? (VERDICT_COLORS[forecastInfo.verdict] || '#6b7280') : '#6b7280' }}
              ></div>
              <span>Forecast</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full border border-gray-400"></div>
              <span>7D / 30D targets</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
