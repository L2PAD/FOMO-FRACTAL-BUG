/**
 * PredictionTab — Sentiment Prediction Terminal
 * Real data from forecast engine + signal engine + dataset entries.
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  TrendingUp, TrendingDown, Minus, RefreshCw, Loader2,
  AlertTriangle, BarChart3, Zap, Shield, Activity
} from 'lucide-react';
import BtcForecastChart from '../../components/prediction/BtcForecastChart';

const API = process.env.REACT_APP_BACKEND_URL;

function fmt$(v) {
  if (v == null) return '\u2014';
  return `$${Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}
function fmtPct(v) {
  if (v == null) return '\u2014';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

const DIR_MAP = {
  LONG: { icon: TrendingUp, color: '#16a34a', label: 'LONG', bg: 'rgba(22,163,106,0.1)' },
  UP: { icon: TrendingUp, color: '#16a34a', label: 'LONG', bg: 'rgba(22,163,106,0.1)' },
  SHORT: { icon: TrendingDown, color: '#dc2626', label: 'SHORT', bg: 'rgba(220,38,38,0.1)' },
  DOWN: { icon: TrendingDown, color: '#dc2626', label: 'SHORT', bg: 'rgba(220,38,38,0.1)' },
  NEUTRAL: { icon: Minus, color: '#64748b', label: 'HOLD', bg: 'rgba(100,116,139,0.1)' },
};

export default function PredictionTab() {
  const [chartData, setChartData] = useState(null);
  const [radarData, setRadarData] = useState(null);
  const [signalStats, setSignalStats] = useState(null);
  const [datasetStats, setDatasetStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [horizon, setHorizon] = useState('7D');
  const [livePrice, setLivePrice] = useState(null);
  const priceRef = useRef(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const chartH = horizon === '1D' ? '7D' : horizon;
      const [chartRes, radarRes, sigRes, dsRes] = await Promise.all([
        fetch(`${API}/api/prediction/exchange/graph4?asset=BTC&horizon=${chartH}`),
        fetch(`${API}/api/radar`),
        fetch(`${API}/api/graph-signals/stats`),
        fetch(`${API}/api/dataset/entries/stats`),
      ]);
      if (chartRes.ok) setChartData(await chartRes.json());
      if (radarRes.ok) setRadarData(await radarRes.json());
      if (sigRes.ok) setSignalStats(await sigRes.json());
      if (dsRes.ok) setDatasetStats(await dsRes.json());
    } catch (e) { console.error('Prediction fetch error:', e); }
    finally { setLoading(false); }
  }, [horizon]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Live BTC price polling
  useEffect(() => {
    const fetchPrice = async () => {
      try {
        const r = await fetch(`${API}/api/prediction/exchange/graph4?asset=BTC&horizon=7D`);
        if (r.ok) { const d = await r.json(); setLivePrice(d.nowPrice); }
      } catch {}
    };
    fetchPrice();
    priceRef.current = setInterval(fetchPrice, 60000);
    return () => clearInterval(priceRef.current);
  }, []);

  const currentPrice = livePrice || chartData?.nowPrice;
  const latestForecast = chartData?.rollingForecasts?.slice(-1)[0];
  const dir = DIR_MAP[latestForecast?.direction] || DIR_MAP.NEUTRAL;
  const DirIcon = dir.icon;

  // Build forecast rows for different horizons from rolling forecasts
  const buildForecastRows = () => {
    if (!chartData?.rollingForecasts?.length) return [];
    const forecasts = chartData.rollingForecasts.filter(f => f.evaluated || f.targetPrice);
    // Deduplicate by id
    const seen = new Set();
    const unique = forecasts.filter(f => {
      if (!f.id || seen.has(f.id)) return false;
      seen.add(f.id);
      return true;
    });
    const latest = unique.slice(-5).reverse();
    return latest.map(f => {
      const d = DIR_MAP[f.direction] || DIR_MAP.NEUTRAL;
      return {
        id: f.id,
        direction: f.direction,
        dirInfo: d,
        target: f.targetPrice,
        move: f.expectedMovePct,
        confidence: f.confidence,
        entry: f.entryPrice,
        evaluated: f.evaluated,
        outcome: f.outcome,
      };
    });
  };

  const forecastRows = buildForecastRows();

  if (loading && !chartData) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div data-testid="prediction-tab" className="px-4 py-4 space-y-4">

      {/* Top Bar: BTC Price + Direction + Confidence */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <div className="text-xs text-gray-400 uppercase">BTC</div>
            <div className="text-2xl font-bold text-gray-900">{fmt$(currentPrice)}</div>
          </div>
          {latestForecast && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg" style={{ background: dir.bg }}>
              <DirIcon className="w-4 h-4" style={{ color: dir.color }} />
              <span className="text-sm font-semibold" style={{ color: dir.color }}>{dir.label}</span>
              <span className="text-xs text-gray-500">{(latestForecast.confidence * 100).toFixed(0)}%</span>
            </div>
          )}
          {chartData?.regime && (
            <div className="text-xs text-gray-400">
              Regime: <span className="font-medium text-gray-600">{chartData.regime.current}</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {['1D', '7D', '30D'].map(h => (
            <button key={h} onClick={() => setHorizon(h)}
              data-testid={`horizon-${h}`}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                horizon === h ? 'bg-gray-900 text-white' : 'text-gray-400 hover:text-gray-700 bg-gray-100'
              }`}>{h}</button>
          ))}
          <button onClick={fetchAll} data-testid="prediction-refresh"
            className="p-1.5 text-gray-400 hover:text-gray-600">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Chart */}
      <div data-testid="prediction-chart" className="bg-white rounded-xl border border-gray-100 overflow-hidden" style={{ height: 340 }}>
        {chartData ? (
          <BtcForecastChart data={chartData} horizon={horizon} hideForecast={horizon === '1D'} />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">No chart data</div>
        )}
      </div>

      {/* Grid: Predictions + Signals + Alts + Model State */}
      <div className="grid grid-cols-2 gap-4">

        {/* Prediction Table */}
        <div data-testid="prediction-table" className="bg-white rounded-xl border border-gray-100 p-4">
          <div className="text-xs font-semibold text-gray-500 uppercase mb-3 flex items-center gap-1.5">
            <BarChart3 className="w-3.5 h-3.5" /> Recent Forecasts
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-400 border-b border-gray-100">
                <th className="text-left py-1.5">Dir</th>
                <th className="text-right py-1.5">Target</th>
                <th className="text-right py-1.5">Move</th>
                <th className="text-right py-1.5">Conf</th>
                <th className="text-right py-1.5">Result</th>
              </tr>
            </thead>
            <tbody>
              {forecastRows.map((r) => (
                <tr key={r.id} className="border-b border-gray-50">
                  <td className="py-2">
                    <span className="font-semibold" style={{ color: r.dirInfo.color }}>{r.dirInfo.label}</span>
                  </td>
                  <td className="text-right text-gray-700">{fmt$(r.target)}</td>
                  <td className="text-right" style={{ color: r.move >= 0 ? '#16a34a' : '#dc2626' }}>{fmtPct(r.move)}</td>
                  <td className="text-right text-gray-500">{(r.confidence * 100).toFixed(0)}%</td>
                  <td className="text-right">
                    {r.evaluated ? (
                      <span style={{ color: r.outcome === 'HIT' ? '#16a34a' : '#dc2626' }}>{r.outcome || '?'}</span>
                    ) : (
                      <span className="text-gray-300">pending</span>
                    )}
                  </td>
                </tr>
              ))}
              {forecastRows.length === 0 && (
                <tr><td colSpan={5} className="text-center text-gray-400 py-4">No forecasts yet</td></tr>
              )}
            </tbody>
          </table>
          {chartData?.stats && (
            <div className="flex gap-4 mt-3 text-xs text-gray-400">
              <span>Win: <b className="text-gray-600">{(chartData.stats.winRate * 100).toFixed(0)}%</b></span>
              <span>DirHit: <b className="text-gray-600">{(chartData.stats.dirHit * 100).toFixed(0)}%</b></span>
              <span>AvgDev: <b className="text-gray-600">{chartData.stats.avgDev?.toFixed(1)}%</b></span>
              <span>Evaluated: <b className="text-gray-600">{chartData.stats.evaluatedCount}</b></span>
            </div>
          )}
        </div>

        {/* Alt Radar (Top Tokens from Signal Engine) */}
        <div data-testid="alt-radar" className="bg-white rounded-xl border border-gray-100 p-4">
          <div className="text-xs font-semibold text-gray-500 uppercase mb-3 flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5" /> Signal Radar (Top Alts)
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-400 border-b border-gray-100">
                <th className="text-left py-1.5">Token</th>
                <th className="text-right py-1.5">Strength</th>
                <th className="text-right py-1.5">Signals</th>
                <th className="text-right py-1.5">Score</th>
              </tr>
            </thead>
            <tbody>
              {(radarData?.hot_tokens || []).slice(0, 10).map((t, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-2 font-medium text-gray-800">{t.token.replace('token:', '')}</td>
                  <td className="text-right">
                    <span className="font-medium" style={{ color: t.strength > 50 ? '#16a34a' : '#d97706' }}>{t.strength}</span>
                  </td>
                  <td className="text-right text-gray-500">{t.signal_count}</td>
                  <td className="text-right">
                    <div className="w-12 h-1.5 bg-gray-100 rounded-full ml-auto">
                      <div className="h-full rounded-full" style={{
                        width: `${Math.min(t.strength, 100)}%`,
                        background: t.strength > 50 ? '#16a34a' : '#d97706'
                      }} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {radarData?.pre_pumps?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="text-xs font-semibold text-red-500 mb-2 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Pre-Pump Alerts
              </div>
              <div className="flex flex-wrap gap-1.5">
                {radarData.pre_pumps.slice(0, 8).map((p, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-600 font-medium">
                    {p.token.replace('token:', '')} {p.score}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom: Signal Engine + Model State + Dataset Health */}
      <div className="grid grid-cols-3 gap-4">

        {/* Signal Engine Summary */}
        <div data-testid="signal-engine-block" className="bg-white rounded-xl border border-gray-100 p-4">
          <div className="text-xs font-semibold text-gray-500 uppercase mb-3 flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5" /> Signal Engine
          </div>
          {signalStats && (
            <div className="space-y-2.5">
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Total Signals</span>
                <span className="font-semibold text-gray-800">{signalStats.total_signals_logged?.toLocaleString()}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Pre-Pump</span>
                <span className="font-semibold text-red-500">{signalStats.by_type?.PRE_PUMP || 0}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Actor Distribution</span>
                <span className="font-semibold text-blue-500">{signalStats.by_type?.ACTOR_DISTRIBUTION || 0}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Fund Pressure</span>
                <span className="font-semibold text-green-500">{signalStats.by_type?.FUND_PRESSURE || 0}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Active Funds</span>
                <span className="font-semibold text-gray-800">{signalStats.active_funds || 0}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Signal Edges</span>
                <span className="font-semibold text-gray-800">{signalStats.signal_edges || 0}</span>
              </div>
            </div>
          )}
        </div>

        {/* Model State */}
        <div data-testid="model-state" className="bg-white rounded-xl border border-gray-100 p-4">
          <div className="text-xs font-semibold text-gray-500 uppercase mb-3 flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5" /> Model State
          </div>
          {chartData?.stats && (
            <div className="space-y-2.5">
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Win Rate</span>
                <span className="font-semibold" style={{ color: chartData.stats.winRate > 0.5 ? '#16a34a' : '#d97706' }}>
                  {(chartData.stats.winRate * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Direction Hit</span>
                <span className="font-semibold" style={{ color: chartData.stats.dirHit > 0.5 ? '#16a34a' : '#d97706' }}>
                  {(chartData.stats.dirHit * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Avg Deviation</span>
                <span className="font-semibold text-gray-800">{chartData.stats.avgDev?.toFixed(2)}%</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Evaluated</span>
                <span className="font-semibold text-gray-800">{chartData.stats.evaluatedCount}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Regime</span>
                <span className="font-semibold text-gray-800">{chartData.regime?.current || 'N/A'}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Regime Conf</span>
                <span className="font-semibold text-gray-600">{((chartData.regime?.confidence || 0) * 100).toFixed(0)}%</span>
              </div>
            </div>
          )}
        </div>

        {/* Dataset Health */}
        <div data-testid="dataset-health" className="bg-white rounded-xl border border-gray-100 p-4">
          <div className="text-xs font-semibold text-gray-500 uppercase mb-3 flex items-center gap-1.5">
            <BarChart3 className="w-3.5 h-3.5" /> Dataset Health
          </div>
          {datasetStats && (
            <div className="space-y-2.5">
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Total Entries</span>
                <span className="font-semibold text-gray-800">{datasetStats.total}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">GOOD</span>
                <span className="font-semibold text-green-500">{datasetStats.dataset_distribution?.good_pct}%</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">NEUTRAL</span>
                <span className="font-semibold text-gray-500">{datasetStats.dataset_distribution?.neutral_pct}%</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">BAD</span>
                <span className="font-semibold text-red-500">{datasetStats.dataset_distribution?.bad_pct}%</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Avg DQS</span>
                <span className="font-semibold text-gray-800">{datasetStats.avg_dqs?.toFixed(3)}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Status</span>
                <span className="font-semibold" style={{
                  color: datasetStats.distribution_health === 'OK' ? '#16a34a'
                    : datasetStats.distribution_health === 'WARNING' ? '#d97706'
                    : datasetStats.distribution_health === 'CRITICAL' ? '#dc2626'
                    : '#64748b'
                }}>{datasetStats.distribution_health}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">ML Ready</span>
                <span className="font-semibold" style={{ color: datasetStats.ready_for_ml ? '#16a34a' : '#d97706' }}>
                  {datasetStats.ready_for_ml ? 'YES' : `${datasetStats.total}/500`}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
