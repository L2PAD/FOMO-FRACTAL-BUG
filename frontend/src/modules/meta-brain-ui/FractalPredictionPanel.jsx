/**
 * FRACTAL PREDICTION PANEL — Mirror of Overview page fractal data
 * Used in Prediction page, Fractal tab.
 * Shows: Chart + Verdict + Action/Reasons/Risks + Horizon Table
 */

import React, { useState, useEffect, useCallback, lazy, Suspense } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  Activity,
  Clock,
  Target,
  RefreshCw,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const LivePredictionChart = lazy(() => import('../../components/charts/LivePredictionChart'));

// ── Helpers ──

const getStanceColor = (s) =>
  s === 'BULLISH' ? 'text-emerald-600' : s === 'BEARISH' ? 'text-red-500' : 'text-gray-500';

const getStanceBgColor = (s) =>
  s === 'BULLISH' ? 'bg-emerald-50' : s === 'BEARISH' ? 'bg-red-50' : 'bg-gray-50';

const getStanceIcon = (s) =>
  s === 'BULLISH' ? <TrendingUp className="w-5 h-5" /> :
  s === 'BEARISH' ? <TrendingDown className="w-5 h-5" /> :
  <Minus className="w-5 h-5" />;

const getSeverityColor = (sev) =>
  sev === 'HIGH' ? 'text-red-600 bg-red-50' :
  sev === 'MEDIUM' ? 'text-amber-600 bg-amber-50' :
  'text-gray-600 bg-gray-50';

const getActionHintText = (hint) => {
  switch (hint) {
    case 'INCREASE_RISK': return 'Increase Risk Exposure';
    case 'REDUCE_RISK': return 'Reduce Risk / Raise Cash';
    case 'HOLD_WAIT': return 'Wait for Confirmation';
    case 'HEDGE': return 'Consider Hedging';
    default: return 'Hold Position';
  }
};

const getActionHintDescription = (hint) => {
  switch (hint) {
    case 'INCREASE_RISK': return 'Market conditions support risk. Consider gradually increasing exposure to growth assets.';
    case 'REDUCE_RISK': return 'Defense mode recommended. Reduce position sizes and increase cash allocation.';
    case 'HOLD_WAIT': return 'Signal strength is weak. Wait for clearer confirmation before acting.';
    case 'HEDGE': return 'Elevated tail risk detected. Consider protective positions or hedges.';
    default: return 'Maintain current allocation. Monitor for changes in market conditions.';
  }
};

// ── Sub-components ──

const VerdictBanner = ({ verdict, horizon }) => {
  if (!verdict) return null;
  const stanceLabel = verdict.stance === 'BULLISH' ? 'Bullish' : verdict.stance === 'BEARISH' ? 'Bearish' : 'HOLD';
  return (
    <div className={`p-5 rounded-lg ${getStanceBgColor(verdict.stance)}`} data-testid="fractal-verdict-banner">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <div className={`p-3 rounded-full ${verdict.stance === 'BULLISH' ? 'bg-emerald-100' : verdict.stance === 'BEARISH' ? 'bg-red-100' : 'bg-gray-100'}`}>
            {getStanceIcon(verdict.stance)}
          </div>
          <div>
            <div className="text-sm text-gray-500 uppercase tracking-wide">
              Fractal &bull; {horizon}d
            </div>
            <div className={`text-3xl font-bold ${getStanceColor(verdict.stance)}`}>
              {stanceLabel}
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-sm text-gray-500">Confidence</div>
          <div className="text-2xl font-semibold text-gray-800">{verdict.confidencePct}%</div>
        </div>
      </div>
      {verdict.summary && <p className="mt-4 text-gray-700">{verdict.summary}</p>}
    </div>
  );
};

const ActionCard = ({ verdict }) => {
  if (!verdict) return null;
  return (
    <div className="p-4 bg-white border border-gray-100 rounded-lg" data-testid="fractal-action-card">
      <div className="flex items-center gap-2 mb-3">
        <Target className="w-4 h-4 text-gray-400" />
        <h3 className="font-semibold text-gray-800 text-sm">What To Do</h3>
      </div>
      <div className={`text-base font-bold mb-2 ${getStanceColor(verdict.stance)}`}>
        {getActionHintText(verdict.actionHint)}
      </div>
      <p className="text-xs text-gray-600">{getActionHintDescription(verdict.actionHint)}</p>
    </div>
  );
};

const ReasonsSection = ({ reasons }) => {
  if (!reasons || reasons.length === 0) return null;
  return (
    <div className="p-4 bg-white border border-gray-100 rounded-lg" data-testid="fractal-reasons">
      <div className="flex items-center gap-2 mb-3">
        <Activity className="w-4 h-4 text-gray-400" />
        <h3 className="font-semibold text-gray-800 text-sm">Why This Verdict</h3>
      </div>
      <div className="space-y-2">
        {reasons.map((r, i) => (
          <div key={i} className="flex items-start gap-2">
            <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded ${getSeverityColor(r.severity)}`}>{r.severity}</span>
            <div>
              <div className="font-medium text-gray-800 text-xs">{r.title}</div>
              <div className="text-xs text-gray-600">{r.text}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const RisksSection = ({ risks }) => (
  <div className="p-4 bg-white border border-gray-100 rounded-lg" data-testid="fractal-risks">
    <div className="flex items-center gap-2 mb-3">
      <AlertTriangle className="w-4 h-4 text-amber-500" />
      <h3 className="font-semibold text-gray-800 text-sm">Key Risks</h3>
    </div>
    {(!risks || risks.length === 0) ? (
      <p className="text-xs text-gray-500">No significant risks identified</p>
    ) : (
      <div className="space-y-2">
        {risks.map((risk, i) => (
          <div key={i} className="flex items-start gap-2">
            <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded ${getSeverityColor(risk.severity)}`}>{risk.severity}</span>
            <div>
              <div className="font-medium text-gray-800 text-xs">{risk.title}</div>
              <div className="text-xs text-gray-600">{risk.text}</div>
            </div>
          </div>
        ))}
      </div>
    )}
  </div>
);

const HorizonTable = ({ horizons }) => {
  if (!horizons || horizons.length === 0) return null;
  return (
    <div className="p-4 bg-white border border-gray-100 rounded-lg" data-testid="fractal-horizon-table">
      <div className="flex items-center gap-2 mb-3">
        <Clock className="w-4 h-4 text-gray-400" />
        <h3 className="font-semibold text-gray-800 text-sm">Forecast by Horizon</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-gray-100 text-xs">
              <th className="pb-2 font-medium">Horizon</th>
              <th className="pb-2 font-medium">Stance</th>
              <th className="pb-2 font-medium">Median</th>
              <th className="pb-2 font-medium">Range</th>
              <th className="pb-2 font-medium">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {horizons.map((h, i) => (
              <tr key={i} className="border-b border-gray-50 last:border-0">
                <td className="py-2 font-medium text-gray-800">
                  {h.days === 'synthetic' ? 'Synthetic' : `${h.days}d`}
                </td>
                <td className={`py-2 font-semibold ${getStanceColor(h.stance)}`}>
                  {h.stance === 'BULLISH' ? 'Bullish' : h.stance === 'BEARISH' ? 'Bearish' : 'HOLD'}
                </td>
                <td className="py-2 text-gray-700">
                  {h.medianProjectionPct >= 0 ? '+' : ''}{h.medianProjectionPct?.toFixed(1)}%
                </td>
                <td className="py-2 text-gray-500">
                  [{h.rangeLowPct?.toFixed(1)}%, {h.rangeHighPct?.toFixed(1)}%]
                </td>
                <td className="py-2">
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${h.confidencePct >= 70 ? 'bg-emerald-500' : h.confidencePct >= 50 ? 'bg-amber-500' : 'bg-gray-400'}`}
                        style={{ width: `${h.confidencePct}%` }}
                      />
                    </div>
                    <span className="text-gray-600">{h.confidencePct}%</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ── Main Panel ──

export default function FractalPredictionPanel({ horizonDays = 7, viewMode = 'candle', children }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Map prediction horizon (1/7/30) to overview horizon
  const overviewHorizon = horizonDays <= 1 ? 7 : horizonDays;

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/ui/overview?asset=btc&horizon=${overviewHorizon}`);
      const json = await res.json();
      if (!json.ok) throw new Error(json.error || 'Failed to fetch fractal data');
      setData(json);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [overviewHorizon]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div className="space-y-4" data-testid="fractal-prediction-panel">
      {/* Chart */}
      <div className="bg-white rounded-xl p-3">
        <Suspense fallback={
          <div className="h-[500px] bg-gray-50 rounded-lg flex items-center justify-center">
            <RefreshCw className="w-6 h-6 text-gray-300 animate-spin" />
          </div>
        }>
          <LivePredictionChart
            asset="BTC"
            horizonDays={overviewHorizon}
            view="crossAsset"
            viewMode={viewMode}
          />
        </Suspense>
      </div>

      {/* Loading */}
      {loading && !data && (
        <div className="p-6 bg-gray-50 rounded-lg animate-pulse">
          <div className="h-8 w-40 bg-gray-200 rounded mb-3" />
          <div className="h-4 w-full bg-gray-200 rounded" />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Data blocks */}
      {data && (
        <>
          <VerdictBanner verdict={data.verdict} horizon={overviewHorizon} />

          {children}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <ActionCard verdict={data.verdict} />
            <ReasonsSection reasons={data.reasons} />
            <RisksSection risks={data.risks} />
          </div>

          <HorizonTable horizons={data.horizons} />
        </>
      )}
    </div>
  );
}
