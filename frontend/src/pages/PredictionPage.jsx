/**
 * BTC Prediction Terminal v4.1 — Rolling Expectation Curve
 * Uses graph4 endpoint. No cone/fan. Clean rolling forecast curve.
 * Right panel: band numbers for 30D, risk profile for 7D.
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  TrendingUp, TrendingDown, Minus, RefreshCw, Loader2,
  AlertTriangle, Clock, Shield, Crosshair, BarChart3
} from 'lucide-react';
import BtcForecastChart from '../components/prediction/BtcForecastChart';

const API = process.env.REACT_APP_BACKEND_URL;

function fmt$(v) {
  if (v == null) return '\u2014';
  return `$${Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}
function fmtPct(v) {
  if (v == null) return '\u2014';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

const DIR = {
  LONG: { icon: TrendingUp, color: '#16a34a', label: 'LONG' },
  UP: { icon: TrendingUp, color: '#16a34a', label: 'LONG' },
  SHORT: { icon: TrendingDown, color: '#dc2626', label: 'SHORT' },
  DOWN: { icon: TrendingDown, color: '#dc2626', label: 'SHORT' },
  NEUTRAL: { icon: Minus, color: '#64748b', label: 'NEUTRAL' },
};

function riskLevel(risk) {
  if (!risk) return { label: 'N/A', color: '#64748b' };
  if (risk.downside > 0.6 || risk.volatility > 10) return { label: 'High', color: '#dc2626' };
  if (risk.downside > 0.4 || risk.volatility > 5) return { label: 'Moderate', color: '#d97706' };
  return { label: 'Low', color: '#16a34a' };
}

function convictionLabel(conf) {
  const pct = conf * 100;
  if (pct >= 70) return 'Strong';
  if (pct >= 50) return 'Moderate';
  if (pct >= 30) return 'Weak';
  return 'Low';
}

export default function PredictionPage() {
  const [data, setData] = useState(null);
  const [heroForecasts, setHeroForecasts] = useState(null);
  const [livePrice, setLivePrice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [horizon, setHorizon] = useState('7D');
  const priceInterval = useRef(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const chartH = horizon === '1D' ? '7D' : horizon;
      const [gRes, fRes] = await Promise.all([
        fetch(`${API}/api/prediction/exchange/graph4?asset=BTC&horizon=${chartH}`),
        fetch(`${API}/api/prediction/exchange/forecast?asset=BTC`),
      ]);
      const gJson = gRes.ok ? await gRes.json() : null;
      const fJson = fRes.ok ? await fRes.json() : null;
      if (gJson?.ok) setData(gJson);
      if (fJson?.ok) {
        const map = {};
        for (const t of fJson.targets || []) map[t.horizon] = t;
        setHeroForecasts(map);
      }
    } catch (e) {
      console.error('[Prediction] fetch error:', e);
    }
    setLoading(false);
  }, [horizon]);

  const fetchLivePrice = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/prediction/exchange/live-price?asset=BTC`);
      const j = r.ok ? await r.json() : null;
      if (j?.ok) setLivePrice(j.price);
    } catch {}
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => {
    fetchLivePrice();
    priceInterval.current = setInterval(fetchLivePrice, 5000);
    return () => clearInterval(priceInterval.current);
  }, [fetchLivePrice]);

  // Band data for 30D (right panel numbers only)
  const band = data?.band;
  const isBandMode = horizon === '30D' && band;

  const HMAP = { '1D': '24H', '7D': '7D', '30D': '30D' };
  const hero = heroForecasts?.[HMAP[horizon]];

  // For band mode: use band data for target display; for point mode: use hero/latest forecast
  const latestForecast = data?.rollingForecasts?.length > 0 ? data.rollingForecasts[data.rollingForecasts.length - 1] : null;
  const target = isBandMode
    ? band.medianTarget
    : (hero?.targetPrice || latestForecast?.targetPrice || 0);
  const conf = isBandMode
    ? (band.signalStrength ? Math.min(0.85, band.signalStrength * 0.7) : 0)
    : (hero?.confidence || latestForecast?.confidence || 0);
  const direction = isBandMode
    ? (band.bias || 'NEUTRAL')
    : (hero?.direction || latestForecast?.direction || 'NEUTRAL');
  const price = livePrice || data?.nowPrice || 0;
  const movePct = price > 0 && target > 0 ? ((target - price) / price) * 100 : 0;

  const dir = DIR[direction] || DIR.NEUTRAL;
  const DirIcon = dir.icon;
  const risk = data?.riskProfile;
  const rl = riskLevel(risk);
  const stats = data?.stats;

  // 1D overlay data
  const oneDayOverlay = horizon === '1D' ? { direction, movePct, color: dir.color } : null;

  if (loading && !data) {
    return (
      <div data-testid="prediction-page" className="flex items-center justify-center" style={{ minHeight: '60vh' }}>
        <Loader2 className="w-6 h-6 animate-spin" style={{ color: '#64748b' }} />
      </div>
    );
  }

  return (
    <div data-testid="prediction-page">
      {/* Header — unified 71px */}
      <div className="border-b border-gray-200 bg-white h-[71px]">
        <div className="px-6 h-full flex items-center">
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-3">
              <Crosshair className="w-5 h-5 text-gray-400" />
              <div>
                <h1 className="text-xl font-bold text-gray-900">Prediction</h1>
                <p className="text-sm text-gray-500">Bitcoin price prediction & forecasting</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {livePrice > 0 && (
                <span className="text-sm font-semibold text-gray-900 tabular-nums">{fmt$(livePrice)}</span>
              )}
              {data?.changePct != null && (
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${data.changePct >= 0 ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                  {fmtPct(data.changePct)}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="px-6 py-3 space-y-3">

      {/* CHART + RIGHT PANEL */}
      <div className="grid gap-3 items-stretch" style={{ gridTemplateColumns: '1fr 300px' }}>

        {/* CHART */}
        <div data-testid="chart-panel" className="rounded-xl overflow-hidden flex flex-col"
          style={{ background: '#fff', border: '1px solid rgba(15,23,42,0.06)' }}>
          <div className="flex items-center justify-between px-4 py-2 shrink-0"
            style={{ borderBottom: '1px solid rgba(15,23,42,0.04)' }}>
            <div className="flex items-center gap-3 text-[10px]" style={{ color: '#94a3b8' }}>
              <span className="flex items-center gap-1">
                <span className="inline-block w-3 h-0.5 rounded" style={{ background: '#16a34a' }} /> Price
              </span>
              {horizon !== '1D' && (
                <span className="flex items-center gap-1">
                  <span className="inline-block w-3 h-0.5 rounded" style={{ background: '#0f172a' }} /> Forecast
                </span>
              )}
              <span className="flex items-center gap-1">
                <span className="inline-block w-[1px] h-3" style={{ background: '#7B61FF' }} /> NOW
              </span>
              {livePrice > 0 && (
                <span className="tabular-nums font-semibold text-[11px] ml-2" style={{ color: '#0f172a' }}>
                  {fmt$(livePrice)}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              <button onClick={fetchData} data-testid="refresh-btn" title="Refresh"
                className="p-1 rounded-md hover:bg-gray-100 transition-colors mr-1" style={{ color: '#94a3b8' }}>
                <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
              </button>
              <div className="flex items-center gap-0.5 p-0.5 rounded-lg" style={{ background: '#f1f5f9' }}>
                {['1D', '7D', '30D'].map(h => (
                  <button key={h} onClick={() => setHorizon(h)} data-testid={`horizon-${h}`}
                    className="px-2.5 py-0.5 rounded text-[11px] font-semibold transition-all"
                    style={{
                      background: horizon === h ? '#fff' : 'transparent',
                      color: horizon === h ? '#0f172a' : '#94a3b8',
                      boxShadow: horizon === h ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
                    }}>
                    {h}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="flex-1">
            {data && (
              <BtcForecastChart
                data={data}
                horizon={horizon === '1D' ? '7D' : horizon}
                hideForecast={horizon === '1D'}
                oneDayOverlay={oneDayOverlay}
              />
            )}
          </div>
        </div>

        {/* RIGHT PANEL */}
        <div data-testid="right-panel" className="rounded-xl flex flex-col"
          style={{ background: '#fff', border: '1px solid rgba(15,23,42,0.06)' }}>

          {/* Target/Median + Direction/Bias + Conviction + Risk */}
          <div className="p-4 space-y-3" style={{ borderBottom: '1px solid rgba(15,23,42,0.04)' }}>
            <div data-testid="panel-target">
              <div className="text-[10px] font-medium uppercase tracking-wider mb-1" style={{ color: '#94a3b8' }}>
                {isBandMode ? '30D Median' : `${horizon} Target`}
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-xl font-bold tabular-nums" style={{ color: movePct >= 0 ? '#16a34a' : '#dc2626' }}>
                  {fmt$(target)}
                </span>
                <span className="text-xs font-semibold tabular-nums" style={{ color: movePct >= 0 ? '#16a34a' : '#dc2626' }}>
                  {fmtPct(movePct)}
                </span>
              </div>
            </div>
            <div className="flex items-center justify-between" data-testid="panel-direction">
              <div>
                <div className="text-[10px] font-medium uppercase tracking-wider mb-0.5" style={{ color: '#94a3b8' }}>
                  {isBandMode ? 'Bias' : 'Direction'}
                </div>
                <div className="flex items-center gap-1">
                  <DirIcon className="w-4 h-4" style={{ color: dir.color }} />
                  <span className="text-sm font-bold" style={{ color: dir.color }}>{dir.label}</span>
                </div>
              </div>
              <div className="text-right">
                <div className="text-[10px] font-medium uppercase tracking-wider mb-0.5" style={{ color: '#94a3b8' }}>Conviction</div>
                <span className="text-sm tabular-nums" data-testid="panel-confidence"
                  style={{ color: '#0f172a' }}>
                  {convictionLabel(conf)} <span className="text-[10px]" style={{ color: '#94a3b8' }}>({Math.round(conf * 100)}%)</span>
                </span>
              </div>
            </div>
            <div data-testid="panel-risk">
              <div className="text-[10px] font-medium uppercase tracking-wider mb-1" style={{ color: '#94a3b8' }}>Risk Profile</div>
              <div className="flex items-center gap-2">
                <div className="w-1 h-4 rounded-full" style={{ background: rl.color }} />
                <span className="text-sm font-medium" style={{ color: rl.color }}>{rl.label}</span>
              </div>
            </div>
          </div>

          {/* Expected Range */}
          {isBandMode && band ? (
            <div className="p-4 space-y-2" style={{ borderBottom: '1px solid rgba(15,23,42,0.04)' }} data-testid="band-range-panel">
              <div className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: '#94a3b8' }}>Expected Range (p25 – p75)</div>
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold tabular-nums" style={{ color: '#dc2626' }}>{fmt$(band.bandCore.low)}</span>
                <span className="text-[10px]" style={{ color: '#cbd5e1' }}>{'\u2014'}</span>
                <span className="text-sm font-bold tabular-nums" style={{ color: '#16a34a' }}>{fmt$(band.bandCore.high)}</span>
              </div>
              <div className="relative h-1.5 rounded-full overflow-hidden" style={{ background: '#f1f5f9' }}>
                <div className="absolute inset-0 rounded-full"
                  style={{ background: 'linear-gradient(90deg, #dc2626 0%, #2563eb 50%, #16a34a 100%)', opacity: 0.15 }} />
                {price > 0 && band.bandCore.low > 0 && band.bandCore.high > band.bandCore.low && (
                  <div className="absolute top-0 bottom-0 w-0.5 rounded" style={{
                    left: `${Math.min(100, Math.max(0, ((price - band.bandCore.low) / (band.bandCore.high - band.bandCore.low)) * 100))}%`,
                    background: '#0f172a',
                  }} />
                )}
              </div>
              <div className="space-y-1 text-[11px]">
                <div className="flex justify-between">
                  <span style={{ color: '#64748b' }}>Wide Low (p10)</span>
                  <span className="font-semibold tabular-nums" style={{ color: '#dc2626' }}>{fmt$(band.bandWide.low)}</span>
                </div>
                <div className="flex justify-between">
                  <span style={{ color: '#64748b' }}>Median</span>
                  <span className="font-semibold tabular-nums" style={{ color: '#2563eb' }}>{fmt$(band.medianTarget)}</span>
                </div>
                <div className="flex justify-between">
                  <span style={{ color: '#64748b' }}>Wide High (p90)</span>
                  <span className="font-semibold tabular-nums" style={{ color: '#16a34a' }}>{fmt$(band.bandWide.high)}</span>
                </div>
              </div>
            </div>
          ) : risk && (
            <div className="p-4 space-y-2" style={{ borderBottom: '1px solid rgba(15,23,42,0.04)' }}>
              <div className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: '#94a3b8' }}>Expected Range</div>
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold tabular-nums" style={{ color: '#dc2626' }}>{fmt$(risk.worstCase)}</span>
                <span className="text-[10px]" style={{ color: '#cbd5e1' }}>{'\u2014'}</span>
                <span className="text-sm font-bold tabular-nums" style={{ color: '#16a34a' }}>{fmt$(risk.bestCase)}</span>
              </div>
              <div className="relative h-1.5 rounded-full overflow-hidden" style={{ background: '#f1f5f9' }}>
                <div className="absolute inset-0 rounded-full"
                  style={{ background: 'linear-gradient(90deg, #dc2626 0%, #d97706 40%, #16a34a 100%)', opacity: 0.2 }} />
              </div>
            </div>
          )}

          {/* Risk Distribution */}
          {risk && (
            <div className="p-4 space-y-2 flex-1" data-testid="risk-distribution-panel">
              <div className="flex items-center gap-2">
                <Shield className="w-3.5 h-3.5" style={{ color: '#64748b' }} />
                <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: '#64748b' }}>Distribution</span>
                <span className="text-[10px] ml-auto tabular-nums" style={{ color: '#94a3b8' }}>n={risk.sampleSize}</span>
              </div>
              <div className="space-y-2">
                <DistBar label="Upside" pct={risk.upside} color="#16a34a" testId="dist-upside" />
                <DistBar label="Neutral" pct={risk.neutral} color="#64748b" testId="dist-neutral" />
                <DistBar label="Downside" pct={risk.downside} color="#dc2626" testId="dist-downside" />
              </div>
            </div>
          )}

          {/* ETA TO TARGET */}
          <div className="p-4 space-y-1" data-testid="eta-to-target-panel" style={{ borderTop: '1px solid rgba(15,23,42,0.04)' }}>
            <div className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: '#64748b' }}>
              ETA to Target
            </div>
            <div className="text-sm font-medium" style={{ color: '#0f172a' }}>
              {data?.etaToTargetDays != null
                ? `~${data.etaToTargetDays} days (historical avg)`
                : 'Insufficient data'}
            </div>
          </div>
        </div>
      </div>

      {/* FORECAST PERFORMANCE */}
      {data?.rollingForecasts?.length > 0 && (
        <div data-testid="forecast-performance-block" className="rounded-xl overflow-hidden"
          style={{ background: '#fff', border: '1px solid rgba(15,23,42,0.06)' }}>

          {stats && (
            <div className="flex items-center gap-6 px-4 py-2" data-testid="summary-bar"
              style={{ borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
              <div className="flex items-center gap-2">
                <BarChart3 className="w-3.5 h-3.5" style={{ color: '#64748b' }} />
                <span className="text-xs font-bold" style={{ color: '#0f172a' }}>Performance</span>
              </div>
              <Stat label="Win Rate" value={`${(stats.winRate * 100).toFixed(0)}%`}
                color={stats.winRate >= 0.5 ? '#16a34a' : stats.winRate >= 0.3 ? '#d97706' : '#dc2626'} />
              <Stat label="Dir Hit" value={`${(stats.dirHit * 100).toFixed(0)}%`}
                color={stats.dirHit >= 0.5 ? '#16a34a' : '#d97706'} />
              <Stat label="Avg Dev" value={`${stats.avgDev.toFixed(1)}%`} color="#0f172a" />
              <Stat label="Eval" value={stats.evaluatedCount} color="#0f172a" />
              {stats.overdue > 0 && (
                <div className="flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" style={{ color: '#d97706' }} />
                  <span className="text-[11px] font-medium tabular-nums" style={{ color: '#d97706' }}>{stats.overdue}</span>
                </div>
              )}
            </div>
          )}

          <div className="overflow-auto">
            <table className="w-full text-[12px]" data-testid="forecast-table">
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
                  {['Eval', 'Dir', 'Entry', 'Target', 'Move', 'Conf', 'Actual', 'Outcome'].map(h => (
                    <th key={h} className={`py-2 px-3 font-semibold text-[10px] uppercase tracking-wider ${
                      ['Dir', 'Outcome'].includes(h) ? 'text-center' : 'text-right'
                    }`} style={{ color: '#94a3b8' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(() => {
                  const seen = new Set();
                  return [...data.rollingForecasts].reverse().filter(f => {
                    if (!f.id || seen.has(f.id)) return false;
                    seen.add(f.id);
                    return true;
                  }).map((f, i) => {
                  const isLatest = i === 0;
                  const fMove = f.expectedMovePct;
                  const isUp = fMove >= 0;
                  const d = DIR[f.direction] || DIR.NEUTRAL;
                  const FIcon = d.icon;
                  const evalMs = f.madeAtTs + f.horizonDays * 86400 * 1000;
                  const eDate = new Date(evalMs);
                  return (
                    <tr key={f.id || `${f.madeAtTs}-${i}`}
                      data-testid={isLatest ? 'row-active' : `row-${i}`}
                      className="transition-colors hover:bg-slate-50/50"
                      style={{
                        borderBottom: '1px solid rgba(15,23,42,0.04)',
                        background: isLatest ? 'rgba(37,99,235,0.02)' : undefined,
                      }}>
                      <td className="py-1.5 px-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          {isLatest && <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#2563eb' }} />}
                          <span className="tabular-nums" style={{ color: isLatest ? '#2563eb' : '#64748b', fontSize: 11 }}>
                            {eDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                          </span>
                        </div>
                      </td>
                      <td className="py-1.5 px-3 text-center">
                        <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold" style={{ color: d.color }}>
                          <FIcon className="w-3 h-3" />{d.label}
                        </span>
                      </td>
                      <td className="py-1.5 px-3 text-right tabular-nums" style={{ color: '#0f172a', fontSize: 11 }}>{fmt$(f.entryPrice)}</td>
                      <td className="py-1.5 px-3 text-right tabular-nums font-medium" style={{ color: isUp ? '#16a34a' : '#dc2626', fontSize: 11 }}>{fmt$(f.targetPrice)}</td>
                      <td className="py-1.5 px-3 text-right tabular-nums" style={{ color: isUp ? '#16a34a' : '#dc2626', fontSize: 11 }}>{fmtPct(fMove)}</td>
                      <td className="py-1.5 px-3 text-right tabular-nums" style={{ color: '#0f172a', fontSize: 11 }}>{Math.round(f.confidence * 100)}%</td>
                      <td className="py-1.5 px-3 text-right tabular-nums" style={{ color: '#0f172a', fontSize: 11 }}>
                        {f.outcome?.realPrice ? fmt$(f.outcome.realPrice) : '\u2014'}
                      </td>
                      <td className="py-1.5 px-3 text-center">
                        {f.outcome ? (
                          <Badge label={f.outcome.label} dirMatch={f.outcome.directionMatch} />
                        ) : (
                          <span className="inline-flex items-center gap-0.5 text-[9px]"
                            style={{ color: '#94a3b8' }}>
                            <Clock className="w-2.5 h-2.5" />pending
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })})()}
              </tbody>
            </table>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}

/* ── Utility components ── */

function Stat({ label, value, color }) {
  return (
    <div className="flex items-center gap-1" data-testid={`stat-${label.toLowerCase().replace(/\s/g, '-')}`}>
      <span className="text-[10px]" style={{ color: '#94a3b8' }}>{label}</span>
      <span className="text-[11px] font-semibold tabular-nums" style={{ color }}>{value}</span>
    </div>
  );
}

function DistBar({ label, pct, color, testId }) {
  return (
    <div className="flex items-center gap-2" data-testid={testId}>
      <span className="text-[11px] w-16" style={{ color: '#64748b' }}>{label}</span>
      <div className="flex-1 h-1.5 rounded-full" style={{ background: '#f1f5f9' }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${Math.round(pct * 100)}%`, background: color, opacity: 0.6 }} />
      </div>
      <span className="text-[11px] tabular-nums w-8 text-right font-medium" style={{ color }}>{Math.round(pct * 100)}%</span>
    </div>
  );
}

function Badge({ label, dirMatch }) {
  return (
    <span className="inline-flex items-center gap-0.5 text-[9px] font-semibold"
      style={{
        color: label === 'TP' ? '#16a34a' : label === 'FP' ? '#dc2626' : '#d97706',
      }}>
      {(dirMatch ? '\u2713' : '\u2717')} {label}
    </span>
  );
}
