/**
 * Block 2: Forecast Chart — lightweight-charts implementation
 * 
 * Real forecast visualization:
 * - Blue line: actual price history
 * - Green/Red segments: active LONG/SHORT forecasts
 * - Gray segments: evaluated (historical) forecasts
 * - Markers: entry (circle), target (arrow), miss (cross)
 * - Gaps between models = honest discontinuities
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { createChart, LineSeries } from 'lightweight-charts';
import { Loader2, Clock, TrendingUp, TrendingDown, Minus } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const DIR_CFG = {
  LONG:    { color: '#16a34a', icon: TrendingUp, label: 'Long' },
  SHORT:   { color: '#dc2626', icon: TrendingDown, label: 'Short' },
  NEUTRAL: { color: '#64748b', icon: Minus, label: 'Neutral' },
};

const STATUS_CFG = {
  PENDING:   { color: '#3b82f6', label: 'Active' },
  ACTIVE:    { color: '#3b82f6', label: 'Active' },
  EVALUATED: { color: '#16a34a', label: 'Evaluated' },
  OVERDUE:   { color: '#d97706', label: 'Overdue' },
};

function fmt$(v) {
  if (!v) return '—';
  return `$${v.toLocaleString('en', { maximumFractionDigits: 0 })}`;
}

export default function ForecastChart({ asset = 'BTC', horizon: externalHorizon }) {
  const [data, setData] = useState(null);
  const [overlay, setOverlay] = useState(null);
  const [loading, setLoading] = useState(true);
  const [horizon, setHorizon] = useState(externalHorizon || '7D');
  const [showML, setShowML] = useState(true);
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [graphRes, mlRes] = await Promise.all([
        fetch(`${API}/api/prediction/exchange/graph?asset=${asset}&horizon=${horizon}&lookback=90`),
        fetch(`${API}/api/ml-overlay/predict?asset=${asset}&horizon=${horizon}`),
      ]);
      const graphJson = graphRes.ok ? await graphRes.json() : null;
      const mlJson = mlRes.ok ? await mlRes.json() : null;
      if (graphJson?.ok) setData(graphJson);
      if (mlJson?.ok) setOverlay(mlJson);
    } catch (e) {
      console.error('ForecastChart fetch error:', e);
    }
    setLoading(false);
  }, [asset, horizon]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Chart rendering
  useEffect(() => {
    if (!data || !chartContainerRef.current) return;

    // Cleanup old chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const container = chartContainerRef.current;
    const chart = createChart(container, {
      width: container.clientWidth,
      height: 320,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#64748b',
        fontSize: 11,
        fontFamily: 'Inter, sans-serif',
      },
      grid: {
        vertLines: { color: 'rgba(15, 23, 42, 0.04)' },
        horzLines: { color: 'rgba(15, 23, 42, 0.04)' },
      },
      rightPriceScale: {
        borderColor: 'rgba(15, 23, 42, 0.08)',
      },
      timeScale: {
        borderColor: 'rgba(15, 23, 42, 0.08)',
        timeVisible: false,
        tickMarkFormatter: (time) => {
          const d = new Date(time * 1000);
          const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
          return `${months[d.getUTCMonth()]} ${d.getUTCDate()}`;
        },
      },
      localization: {
        timeFormatter: (time) => {
          const d = new Date(time * 1000);
          const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
          return `${months[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;
        },
        priceFormatter: (price) => `$${price.toLocaleString('en', { maximumFractionDigits: 0 })}`,
      },
      crosshair: {
        vertLine: { color: 'rgba(15, 23, 42, 0.1)', width: 1, style: 3 },
        horzLine: { color: 'rgba(15, 23, 42, 0.1)', width: 1, style: 3 },
      },
      handleScroll: true,
      handleScale: true,
    });

    chartRef.current = chart;

    // 1) Price series (blue line)
    const priceSeries = chart.addSeries(LineSeries, {
      color: '#3b82f6',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
    });
    priceSeries.setData(data.priceSeries);

    // 2) FOCUS mode: show only last evaluated + current active (institutional clean)
    const segments = data.forecastSegments || [];

    // Pick the last evaluated and the latest active
    const evaluatedSegs = segments
      .filter(s => s.status === 'EVALUATED')
      .sort((a, b) => a.evaluateAfter - b.evaluateAfter);
    const lastEvaluated = evaluatedSegs.at(-1);

    const activeSegs = segments
      .filter(s => s.status === 'ACTIVE')
      .sort((a, b) => b.createdAt - a.createdAt);
    const activeSegment = activeSegs[0];

    // Draw last evaluated (gray dashed)
    if (lastEvaluated) {
      const histSeries = chart.addSeries(LineSeries, {
        color: '#9ca3af',
        lineWidth: 2,
        lineStyle: 2, // dashed
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      histSeries.setData([
        { time: lastEvaluated.createdAt, value: lastEvaluated.entryPrice },
        { time: lastEvaluated.evaluateAfter, value: lastEvaluated.targetPrice },
      ]);
    }

    // Draw active forecast (colored solid, thick)
    if (activeSegment) {
      const activeColor = activeSegment.direction === 'LONG' ? '#16a34a'
        : activeSegment.direction === 'SHORT' ? '#dc2626'
        : '#64748b';

      const activeSeries = chart.addSeries(LineSeries, {
        color: activeColor,
        lineWidth: 3,
        lineStyle: 0, // solid
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      activeSeries.setData([
        { time: activeSegment.createdAt, value: activeSegment.entryPrice },
        { time: activeSegment.evaluateAfter, value: activeSegment.targetPrice },
      ]);
    }

    // Regime shift vertical line (purple dotted) - use 1s offset for ascending time
    if (lastEvaluated && activeSegment) {
      const shiftTime = activeSegment.createdAt;
      const allPrices = data.priceSeries.map(p => p.value);
      const minP = Math.min(...allPrices) * 0.998;
      const maxP = Math.max(...allPrices) * 1.002;

      const shiftSeries = chart.addSeries(LineSeries, {
        color: '#a855f7',
        lineWidth: 1,
        lineStyle: 3, // dotted
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      shiftSeries.setData([
        { time: shiftTime - 1, value: minP },
        { time: shiftTime, value: maxP },
      ]);
    }

    // ML Overlay target line (dashed, lighter green/red)
    if (showML && overlay && activeSegment && overlay.finalTarget) {
      const mlColor = overlay.finalReturn >= 0 ? '#22c55e' : '#f87171';
      const mlSeries = chart.addSeries(LineSeries, {
        color: mlColor,
        lineWidth: 2,
        lineStyle: 2, // dashed
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      mlSeries.setData([
        { time: activeSegment.createdAt, value: activeSegment.entryPrice },
        { time: activeSegment.evaluateAfter, value: overlay.finalTarget },
      ]);
    }

    // Fit content
    chart.timeScale().fitContent();

    // Resize handler
    const resizeObserver = new ResizeObserver((entries) => {
      if (entries.length > 0) {
        const { width } = entries[0].contentRect;
        chart.applyOptions({ width });
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [data, overlay, showML]);

  // Stats from all segments (shown in bar) but chart renders only focus
  const allSegments = data?.forecastSegments || [];
  const evaluatedAll = allSegments.filter(s => s.status === 'EVALUATED');
  const hitCount = evaluatedAll.filter(s => s.hit).length;
  const winRate = evaluatedAll.length > 0 ? hitCount / evaluatedAll.length : 0;
  const lastPrice = data?.priceSeries?.length ? data.priceSeries[data.priceSeries.length - 1].value : 0;

  // Focus segments for active targets table
  const activeTargets = allSegments
    .filter(s => s.status === 'ACTIVE')
    .sort((a, b) => b.createdAt - a.createdAt)
    .slice(0, 1); // Only the latest active

  return (
    <div data-testid="forecast-chart-block" className="space-y-4">
      {/* Chart container */}
      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid rgba(15,23,42,0.06)', padding: '16px 16px 8px' }}>
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>{asset} Forecast</span>
            {/* Horizon pills */}
            <div className="flex items-center gap-0.5 bg-gray-100 rounded-lg p-0.5">
              {['24H', '7D', '30D'].map(h => (
                <button
                  key={h}
                  onClick={() => setHorizon(h)}
                  data-testid={`chart-horizon-${h}`}
                  className={`px-2 py-0.5 rounded text-[11px] font-medium transition-all ${
                    horizon === h ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {h}
                </button>
              ))}
            </div>
            {/* Stage badge */}
            {(() => {
              const stage = overlay?.stage || 'SHADOW';
              const isLive = stage !== 'SHADOW';
              const stageLabels = { SHADOW: 'SHADOW', LIVE_LITE: 'LIVE 50%', LIVE_MED: 'LIVE 75%', LIVE_FULL: 'LIVE 100%' };
              return (
                <span data-testid="stage-badge"
                  className="inline-flex items-center gap-1 text-[10px] font-semibold tracking-wide"
                  style={{
                    color: isLive ? '#16a34a' : '#7c3aed',
                  }}>
                  ML {stageLabels[stage] || stage}
                </span>
              );
            })()}
            {/* Effective alpha */}
            {overlay?.effectiveAlpha != null && overlay.effectiveAlpha > 0 && (
              <span data-testid="effective-alpha-badge" className="text-[9px] font-medium tabular-nums"
                style={{ color: '#2563eb' }}>
                alpha {(overlay.effectiveAlpha * 100).toFixed(0)}%
              </span>
            )}
            {/* ML toggle */}
            {overlay?.ok && (
              <button
                data-testid="ml-overlay-toggle"
                onClick={() => setShowML(v => !v)}
                className="text-[10px] font-medium transition-all"
                style={{
                  color: showML ? '#16a34a' : '#94a3b8',
                }}
              >
                {showML ? 'ML ON' : 'ML OFF'}
              </button>
            )}
          </div>
          <div className="flex items-center gap-4">
            {/* Drift weight indicator */}
            {overlay?.driftWeight != null && overlay.driftWeight < 1.0 && (
              <span data-testid="drift-weight-indicator" className="text-[10px] font-medium tabular-nums"
                style={{ color: '#d97706' }}>
                ML wt {(overlay.driftWeight * 100).toFixed(0)}%
              </span>
            )}
            {/* Legend */}
            <div className="flex items-center gap-3 text-[11px]">
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 rounded" style={{ background: '#3b82f6', display: 'inline-block' }} /> Price</span>
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 rounded" style={{ background: '#16a34a', display: 'inline-block' }} /> Rule</span>
              {showML && <span className="flex items-center gap-1"><span className="w-3 h-0.5 rounded" style={{ background: '#22c55e', display: 'inline-block', opacity: 0.7, borderTop: '1px dashed #22c55e' }} /> ML</span>}
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 rounded" style={{ background: '#9ca3af', display: 'inline-block', borderTop: '1px dashed #9ca3af' }} /> Prev</span>
            </div>
            {lastPrice > 0 && (
              <span className="tabular-nums font-bold" style={{ fontSize: 15, color: '#0f172a' }}>{fmt$(lastPrice)}</span>
            )}
          </div>
        </div>

        {/* Chart */}
        {loading ? (
          <div className="flex items-center justify-center h-[320px]" data-testid="forecast-chart-loading">
            <Loader2 className="w-5 h-5 animate-spin" style={{ color: '#94a3b8' }} />
          </div>
        ) : (
          <div ref={chartContainerRef} data-testid="forecast-chart-canvas" style={{ height: 320 }} />
        )}

        {/* Mini stats */}
        {data && (
          <div className="flex items-center gap-5 mt-2 pt-2" style={{ borderTop: '1px solid rgba(15,23,42,0.04)' }}>
            <Stat label="Segments" value={allSegments.length} />
            <Stat label="Evaluated" value={evaluatedAll.length} />
            <Stat label="Win Rate" value={`${(winRate * 100).toFixed(0)}%`}
              color={winRate >= 0.5 ? '#16a34a' : winRate >= 0.3 ? '#d97706' : '#dc2626'} />
            <Stat label="Active" value={activeTargets.length} color="#3b82f6" />
            {overlay?.mlCorrection != null && (
              <Stat label="ML Corr"
                value={`${overlay.mlCorrection >= 0 ? '+' : ''}${(overlay.mlCorrection * 100).toFixed(2)}%`}
                color={overlay.mlCorrection >= 0 ? '#16a34a' : '#dc2626'} />
            )}
          </div>
        )}
      </div>

      {/* Active Targets Table */}
      {activeTargets.length > 0 && (
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid rgba(15,23,42,0.06)' }} data-testid="forecast-targets-table">
          <div className="px-4 py-3" style={{ borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>Active Targets</span>
          </div>
          <div className="overflow-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
                  <th className="text-left py-2 px-4 font-semibold" style={{ color: '#64748b' }}>Dir</th>
                  <th className="text-right py-2 px-4 font-semibold" style={{ color: '#64748b' }}>Entry</th>
                  <th className="text-right py-2 px-4 font-semibold" style={{ color: '#64748b' }}>Target</th>
                  <th className="text-right py-2 px-4 font-semibold" style={{ color: '#64748b' }}>Move</th>
                  <th className="text-right py-2 px-4 font-semibold" style={{ color: '#64748b' }}>Conf</th>
                  <th className="text-center py-2 px-4 font-semibold" style={{ color: '#64748b' }}>Eval At</th>
                </tr>
              </thead>
              <tbody>
                {activeTargets.map((t) => {
                  const dir = DIR_CFG[t.direction] || DIR_CFG.NEUTRAL;
                  const DirIcon = dir.icon;
                  const movePct = t.entryPrice > 0
                    ? ((t.targetPrice - t.entryPrice) / t.entryPrice * 100)
                    : 0;
                  const evalDate = new Date(t.evaluateAfter * 1000);
                  return (
                    <tr key={t.id} className="hover:bg-slate-50/50 transition-colors"
                      style={{ borderBottom: '1px solid rgba(15,23,42,0.04)' }}
                      data-testid={`active-target-${t.id}`}>
                      <td className="py-2.5 px-4">
                        <span className="flex items-center gap-1" style={{ color: dir.color }}>
                          <DirIcon className="w-3.5 h-3.5" />
                          {dir.label}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-right tabular-nums" style={{ color: '#0f172a' }}>{fmt$(t.entryPrice)}</td>
                      <td className="py-2.5 px-4 text-right tabular-nums font-medium" style={{ color: dir.color }}>{fmt$(t.targetPrice)}</td>
                      <td className="py-2.5 px-4 text-right tabular-nums" style={{ color: movePct >= 0 ? '#16a34a' : '#dc2626' }}>
                        {movePct >= 0 ? '+' : ''}{movePct.toFixed(2)}%
                      </td>
                      <td className="py-2.5 px-4 text-right tabular-nums" style={{ color: '#0f172a' }}>
                        {Math.round(t.confidence * 100)}%
                      </td>
                      <td className="py-2.5 px-4 text-center">
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium"
                          style={{ color: '#3b82f6' }}>
                          <Clock className="w-3 h-3" />
                          {evalDate.toLocaleDateString('en', { month: 'short', day: 'numeric' })}
                        </span>
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

function Stat({ label, value, color = '#0f172a' }) {
  return (
    <div className="flex items-center gap-1.5">
      <span style={{ fontSize: 11, color: '#94a3b8' }}>{label}</span>
      <span className="tabular-nums font-semibold" style={{ fontSize: 12, color }}>{value}</span>
    </div>
  );
}
