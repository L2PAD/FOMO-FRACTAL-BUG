/**
 * Exchange Forecast Chart V3 — Final
 * 
 * Chart: Price (green) + NOW overlay div (purple vertical) + Rolling forecast (black)
 * Summary: WinRate / DirHit / AvgDev / Evaluated / Overdue
 * Table: 10 columns (no Drift, no ECE)
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createChart, LineSeries } from 'lightweight-charts';
import { Loader2, Clock, TrendingUp, TrendingDown, Minus, AlertTriangle, RefreshCw } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

function fmt$(v) {
  if (v == null) return '—';
  return `$${Number(v).toLocaleString('en', { maximumFractionDigits: 0 })}`;
}

function fmtPct(v) {
  if (v == null) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

const DIR_MAP = {
  LONG: { icon: TrendingUp, color: '#16a34a', label: 'LONG' },
  UP: { icon: TrendingUp, color: '#16a34a', label: 'UP' },
  SHORT: { icon: TrendingDown, color: '#dc2626', label: 'SHORT' },
  DOWN: { icon: TrendingDown, color: '#dc2626', label: 'DOWN' },
  NEUTRAL: { icon: Minus, color: '#64748b', label: 'NEUT' },
};

export default function ExchangeForecastChartV3({ asset = 'BTC', onRefresh }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [horizon, setHorizon] = useState('7D');
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const nowOverlayRef = useRef(null);
  const dotOverlayRef = useRef(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/prediction/exchange/graph3?asset=${asset}&horizon=${horizon}&lookback=90`);
      const json = res.ok ? await res.json() : null;
      if (json?.ok) setData(json);
    } catch (e) {
      console.error('[ChartV3] fetch error:', e);
    }
    setLoading(false);
  }, [asset, horizon]);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    if (!data || !chartContainerRef.current) return;

    // Cleanup previous
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }
    if (nowOverlayRef.current) {
      nowOverlayRef.current.remove();
      nowOverlayRef.current = null;
    }
    if (dotOverlayRef.current) {
      dotOverlayRef.current.remove();
      dotOverlayRef.current = null;
    }

    const container = chartContainerRef.current;
    const chart = createChart(container, {
      width: container.clientWidth,
      height: 320,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#64748b',
        fontSize: 11,
        fontFamily: 'Inter, system-ui, sans-serif',
      },
      grid: {
        vertLines: { color: 'rgba(15, 23, 42, 0.04)' },
        horzLines: { color: 'rgba(15, 23, 42, 0.04)' },
      },
      rightPriceScale: { borderColor: 'rgba(15, 23, 42, 0.08)' },
      timeScale: {
        borderColor: 'rgba(15, 23, 42, 0.08)',
        timeVisible: false,
        tickMarkFormatter: (time) => {
          const d = new Date(time * 1000);
          const m = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
          return `${m[d.getUTCMonth()]} ${d.getUTCDate()}`;
        },
      },
      localization: {
        priceFormatter: (p) => `$${p.toLocaleString('en', { maximumFractionDigits: 0 })}`,
      },
      crosshair: {
        vertLine: { color: 'rgba(15, 23, 42, 0.1)', width: 1, style: 3 },
        horzLine: { color: 'rgba(15, 23, 42, 0.1)', width: 1, style: 3 },
      },
      handleScroll: true,
      handleScale: true,
    });
    chartRef.current = chart;

    const { priceSeries, rollingForecasts, nowTs } = data;
    const nowSec = Math.floor(nowTs / 1000);

    // === Layer 1: Price (green) ===
    const priceLine = chart.addSeries(LineSeries, {
      color: '#16a34a',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
    });
    priceLine.setData(priceSeries.map(pt => ({
      time: Math.floor(pt.t / 1000),
      value: pt.p,
    })));

    // === Layer 2: Rolling forecast (black line) ===
    // Start from NOW price point, then rolling targets
    if (rollingForecasts.length > 0) {
      // Bridge: first point = NOW (connects price line to forecast)
      const forecastMap = new Map();
      forecastMap.set(nowSec, data.nowPrice); // start from NOW
      for (const f of rollingForecasts) {
        const t = Math.floor(f.evalTs / 1000);
        forecastMap.set(t, f.finalTarget);
      }
      const forecastData = [...forecastMap.entries()]
        .sort((a, b) => a[0] - b[0])
        .map(([t, v]) => ({ time: t, value: v }));

      if (forecastData.length > 0) {
        const forecastLine = chart.addSeries(LineSeries, {
          color: '#0f172a',
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: true,
          crosshairMarkerVisible: true,
          crosshairMarkerRadius: 3,
        });
        forecastLine.setData(forecastData);
        container._forecastLine = forecastLine; // store for rAF sync loop

        // Collect dot positions with labels
        const dotPoints = [];
        const lastForecastPoint = forecastData[forecastData.length - 1];

        if (horizon === '30D' && forecastData.length > 2) {
          // Find the point closest to 7 days from NOW
          const sevenDaysSec = nowSec + 7 * 86400;
          let closest = null;
          let closestDist = Infinity;
          for (const pt of forecastData) {
            if (pt.time <= nowSec) continue;
            const dist = Math.abs(pt.time - sevenDaysSec);
            if (dist < closestDist) {
              closestDist = dist;
              closest = pt;
            }
          }
          if (closest && closest.time !== lastForecastPoint.time) {
            dotPoints.push({ ...closest, label: '7D' });
          }
          dotPoints.push({ ...lastForecastPoint, label: '30D' });
        } else {
          dotPoints.push({ ...lastForecastPoint, label: horizon });
        }

        // Draw hollow circles + labels — repositioned via rAF loop (sync with scroll/zoom)
        const dotElements = { circles: [], labels: [] };

        // Pre-create DOM elements once
        for (const pt of dotPoints) {
          const dot = document.createElement('div');
          dot.style.position = 'absolute';
          dot.style.width = '8px';
          dot.style.height = '8px';
          dot.style.borderRadius = '50%';
          dot.style.border = '2px solid #0f172a';
          dot.style.background = '#ffffff';
          dot.style.pointerEvents = 'none';
          dot.style.zIndex = '11';
          dot.style.display = 'none';
          dot.setAttribute('data-testid', 'v3-endpoint-dot');
          container.appendChild(dot);
          dotElements.circles.push({ el: dot, time: pt.time, value: pt.value });

          const lbl = document.createElement('div');
          lbl.style.position = 'absolute';
          lbl.style.fontSize = '10px';
          lbl.style.fontWeight = '600';
          lbl.style.color = '#0f172a';
          lbl.style.pointerEvents = 'none';
          lbl.style.zIndex = '12';
          lbl.style.whiteSpace = 'nowrap';
          lbl.style.display = 'none';
          lbl.textContent = pt.label;
          container.appendChild(lbl);
          dotElements.labels.push({ el: lbl, time: pt.time, value: pt.value });
        }

        // Store for cleanup
        container._dotEls = dotElements;
      }
    }

    chart.timeScale().fitContent();

    // === NOW vertical line — pre-create DOM ===
    const nowWrapper = document.createElement('div');
    nowWrapper.style.position = 'absolute';
    nowWrapper.style.top = '0';
    nowWrapper.style.bottom = '30px';
    nowWrapper.style.width = '1px';
    nowWrapper.style.pointerEvents = 'none';
    nowWrapper.style.zIndex = '10';
    nowWrapper.style.display = 'none';
    nowWrapper.setAttribute('data-testid', 'v3-now-line');

    const nowLabel = document.createElement('div');
    nowLabel.style.position = 'absolute';
    nowLabel.style.top = '0';
    nowLabel.style.left = '50%';
    nowLabel.style.transform = 'translateX(-50%)';
    nowLabel.style.fontSize = '9px';
    nowLabel.style.fontWeight = '700';
    nowLabel.style.color = '#7B61FF';
    nowLabel.style.letterSpacing = '0.5px';
    nowLabel.textContent = 'NOW';
    nowWrapper.appendChild(nowLabel);

    const nowLine = document.createElement('div');
    nowLine.style.position = 'absolute';
    nowLine.style.top = '14px';
    nowLine.style.bottom = '0';
    nowLine.style.width = '0';
    nowLine.style.borderLeft = '1px dashed #7B61FF';
    nowLine.style.opacity = '0.7';
    nowWrapper.appendChild(nowLine);

    container.style.position = 'relative';
    container.appendChild(nowWrapper);
    nowOverlayRef.current = nowWrapper;

    // === rAF loop: reposition ALL overlays every frame ===
    let rafId = null;
    const forecastLineRef = chart.addLineSeries ? null : null; // placeholder
    // We need a reference to the forecastLine for priceToCoordinate
    // Store it on container for the loop
    const syncOverlays = () => {
      // NOW line
      const nx = chart.timeScale().timeToCoordinate(nowSec);
      if (nx !== null && nx >= 0) {
        nowWrapper.style.left = `${nx}px`;
        nowWrapper.style.display = '';
      } else {
        nowWrapper.style.display = 'none';
      }

      // Dots + labels
      const dotEls = container._dotEls;
      if (dotEls && container._forecastLine) {
        const fl = container._forecastLine;
        for (let i = 0; i < dotEls.circles.length; i++) {
          const c = dotEls.circles[i];
          const l = dotEls.labels[i];
          const x = chart.timeScale().timeToCoordinate(c.time);
          const y = fl.priceToCoordinate(c.value);
          if (x !== null && y !== null && x >= 0 && y >= 0) {
            c.el.style.left = `${x - 4}px`;
            c.el.style.top = `${y - 4}px`;
            c.el.style.display = '';
            l.el.style.left = `${x + 6}px`;
            l.el.style.top = `${y - 14}px`;
            l.el.style.display = '';
          } else {
            c.el.style.display = 'none';
            l.el.style.display = 'none';
          }
        }
      }

      rafId = requestAnimationFrame(syncOverlays);
    };
    rafId = requestAnimationFrame(syncOverlays);

    // Resize
    const ro = new ResizeObserver(entries => {
      if (entries.length > 0) {
        chart.applyOptions({ width: entries[0].contentRect.width });
      }
    });
    ro.observe(container);

    return () => {
      if (rafId) cancelAnimationFrame(rafId);
      ro.disconnect();
      if (nowOverlayRef.current) {
        nowOverlayRef.current.remove();
        nowOverlayRef.current = null;
      }
      if (container._dotEls) {
        container._dotEls.circles.forEach(c => c.el.remove());
        container._dotEls.labels.forEach(l => l.el.remove());
        container._dotEls = null;
      }
      dotOverlayRef.current = null;
      chart.remove();
      chartRef.current = null;
    };
  }, [data]);

  const ml = data?.ml;
  const summary = data?.summary;

  return (
    <div data-testid="forecast-chart-v3" className="space-y-3">
      {/* Chart Card */}
      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid rgba(15,23,42,0.06)', padding: '16px 16px 8px' }}>
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>{asset} Forecast</span>
            <button onClick={() => { fetchData(); if (onRefresh) onRefresh(); }}
              data-testid="v3-refresh" title="Refresh"
              className="p-1 rounded hover:bg-gray-100 transition-colors" style={{ color: '#94a3b8' }}>
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
            <div className="flex items-center gap-0.5 bg-gray-100 rounded-lg p-0.5">
              {['7D', '30D'].map(h => (
                <button key={h} onClick={() => setHorizon(h)}
                  data-testid={`v3-horizon-${h}`}
                  className={`px-2.5 py-0.5 rounded text-[11px] font-medium transition-all ${
                    horizon === h ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                  }`}>{h}</button>
              ))}
            </div>
            {ml && (
              <span data-testid="v3-stage-badge"
                className="inline-flex items-center gap-1 text-[10px] font-semibold tracking-wide"
                style={{
                  color: ml.stage !== 'SHADOW' ? '#16a34a' : '#7c3aed',
                }}>ML {ml.stage === 'SHADOW' ? 'SHADOW' : ml.stage.replace('LIVE_', '')}</span>
            )}
            {ml?.mlWeight != null && ml.mlWeight < 1.0 && (
              <span data-testid="v3-ml-weight" className="text-[9px] font-medium tabular-nums"
                style={{ color: '#d97706' }}>
                wt {(ml.mlWeight * 100).toFixed(0)}%
              </span>
            )}
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3 text-[10px]" style={{ color: '#94a3b8' }}>
              <span className="flex items-center gap-1">
                <span className="inline-block w-3 h-0.5 rounded" style={{ background: '#16a34a' }} /> Price
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block w-3 h-0.5 rounded" style={{ background: '#0f172a' }} /> Forecast
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block w-[1px] h-3" style={{ background: '#7B61FF' }} /> NOW
              </span>
            </div>
            {data?.nowPrice > 0 && (
              <span className="tabular-nums font-bold" style={{ fontSize: 15, color: '#0f172a' }}>{fmt$(data.nowPrice)}</span>
            )}
          </div>
        </div>

        {/* Chart */}
        {loading ? (
          <div className="flex items-center justify-center h-[320px]" data-testid="v3-chart-loading">
            <Loader2 className="w-5 h-5 animate-spin" style={{ color: '#94a3b8' }} />
          </div>
        ) : (
          <div ref={chartContainerRef} data-testid="v3-chart-canvas" style={{ height: 320, position: 'relative' }} />
        )}
      </div>

      {/* Summary + Table Card */}
      {data?.rollingForecasts?.length > 0 && (
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid rgba(15,23,42,0.06)' }}
          data-testid="v3-forecast-table">

          {/* Summary row */}
          {summary && (
            <div className="flex items-center gap-6 px-4 py-2.5" data-testid="v3-summary-bar"
              style={{ borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#0f172a' }}>Forecast Performance</span>
              <div className="flex items-center gap-1.5">
                <span style={{ color: '#64748b', fontSize: 11 }}>Win Rate</span>
                <span className="font-bold tabular-nums text-[13px]" data-testid="v3-win-rate"
                  style={{ color: summary.winRate >= 0.5 ? '#16a34a' : summary.winRate >= 0.3 ? '#d97706' : '#dc2626' }}>
                  {(summary.winRate * 100).toFixed(0)}%
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span style={{ color: '#64748b', fontSize: 11 }}>Dir Hit</span>
                <span className="font-bold tabular-nums text-[13px]" data-testid="v3-dir-hit"
                  style={{ color: summary.dirHitRate >= 0.5 ? '#16a34a' : '#d97706' }}>
                  {(summary.dirHitRate * 100).toFixed(0)}%
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span style={{ color: '#64748b', fontSize: 11 }}>Avg Dev</span>
                <span className="font-medium tabular-nums text-[13px]" style={{ color: '#0f172a' }}>
                  {summary.avgDeviation.toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span style={{ color: '#64748b', fontSize: 11 }}>Evaluated</span>
                <span className="font-medium tabular-nums text-[13px]" style={{ color: '#0f172a' }}>{summary.evaluated}</span>
              </div>
              {summary.overdue > 0 && (
                <div className="flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" style={{ color: '#d97706' }} />
                  <span className="font-medium tabular-nums text-[11px]" style={{ color: '#d97706' }}>
                    {summary.overdue} overdue
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Table — 10 columns */}
          <div className="overflow-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
                  {['Eval', 'Dir', 'Entry', 'Target', 'Move', 'Conf', 'Weight', 'Stage', 'Actual', 'Outcome'].map(h => (
                    <th key={h} className={`py-2 px-3 font-semibold text-[10px] ${['Dir', 'Stage', 'Outcome'].includes(h) ? 'text-center' : 'text-right'}`}
                      style={{ color: '#94a3b8' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...data.rollingForecasts].reverse().map((f, i) => {
                  const isLatest = i === 0;
                  const movePct = f.entryPrice > 0 ? ((f.finalTarget - f.entryPrice) / f.entryPrice) * 100 : 0;
                  const isUp = f.finalTarget >= f.entryPrice;
                  const dir = DIR_MAP[f.direction] || DIR_MAP.NEUTRAL;
                  const DirIcon = dir.icon;
                  const evalDate = f.evalTs ? new Date(f.evalTs) : null;

                  return (
                    <tr key={f.createdBucket + f.evalTs}
                      data-testid={isLatest ? 'v3-row-active' : `v3-row-${i}`}
                      className="transition-colors hover:bg-gray-50/50"
                      style={{
                        borderBottom: '1px solid rgba(15,23,42,0.04)',
                        background: isLatest ? 'rgba(37, 99, 235, 0.03)' : undefined,
                      }}>
                      <td className="py-2 px-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          {isLatest && <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />}
                          <span className="tabular-nums" style={{ color: isLatest ? '#2563eb' : '#64748b' }}>
                            {evalDate ? evalDate.toLocaleDateString('en', { month: 'short', day: 'numeric' }) : '—'}
                          </span>
                        </div>
                      </td>
                      <td className="py-2 px-3 text-center">
                        <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold" style={{ color: dir.color }}>
                          <DirIcon className="w-3 h-3" />{dir.label}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums" style={{ color: '#0f172a' }}>{fmt$(f.entryPrice)}</td>
                      <td className="py-2 px-3 text-right tabular-nums font-medium" style={{ color: isUp ? '#16a34a' : '#dc2626' }}>{fmt$(f.finalTarget)}</td>
                      <td className="py-2 px-3 text-right tabular-nums" style={{ color: isUp ? '#16a34a' : '#dc2626' }}>{fmtPct(movePct)}</td>
                      <td className="py-2 px-3 text-right tabular-nums" style={{ color: '#0f172a' }}>{Math.round(f.confidence * 100)}%</td>
                      <td className="py-2 px-3 text-right tabular-nums" style={{ color: '#64748b' }}>
                        {isLatest && ml ? `${(ml.mlWeight * 100).toFixed(0)}%` : '—'}
                      </td>
                      <td className="py-2 px-3 text-center">
                        {isLatest && ml ? (
                          <span className="text-[9px] font-semibold"
                            style={{
                              color: ml.stage === 'SHADOW' ? '#7c3aed' : '#16a34a',
                            }}>{ml.stage === 'SHADOW' ? 'SHADOW' : ml.stage.replace('LIVE_', '')}</span>
                        ) : '—'}
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums" style={{ color: '#0f172a' }}>
                        {f.actual != null ? fmt$(f.actual) : '—'}
                      </td>
                      <td className="py-2 px-3 text-center">
                        {f.outcomeLabel ? (
                          <OutcomeBadge label={f.outcomeLabel} dirMatch={f.directionMatch} />
                        ) : (
                          <span className="inline-flex items-center gap-0.5 text-[9px]"
                            style={{ color: '#94a3b8' }}>
                            <Clock className="w-2.5 h-2.5" />pending
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function OutcomeBadge({ label, dirMatch }) {
  const styles = {
    TP: { color: '#16a34a' },
    WEAK: { color: '#d97706' },
    FP: { color: '#dc2626' },
  };
  const s = styles[label] || styles.FP;
  return (
    <span data-testid={`outcome-${label}`}
      className="inline-flex items-center gap-0.5 text-[9px] font-bold"
      style={{ color: s.color }}>
      {dirMatch != null && (dirMatch ? '✓' : '✗')} {label}
    </span>
  );
}
