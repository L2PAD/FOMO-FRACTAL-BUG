/**
 * Analytics Workspace
 *
 * PHASE 4 (2026-04-30) — cut-first, build-second.
 *
 * Cut from this screen entirely:
 *   • LearningInsightsPanel        — empty, ML lifecycle ≠ trader value
 *   • DynamicRiskAnalyticsPanel    — engine internal (R1)
 *   • AdaptiveRiskAnalyticsPanel   — engine internal (R2)
 *   • ExecutionAnalyticsPanel      — order-engine latency
 *   • SafetyAnalyticsPanel         — safety-rules counters
 *   • DecisionAnalyticsPanel.System column
 *     (Operator Override / R2 Active / Source TA / Source Manual / Total Traces)
 *   • Duplicate metrics — Win Rate, PnL, Total appeared in 2-3 places.
 *
 * Single source of trading truth: /api/analytics/decision-quality
 * The only field still pulled from /api/analytics/decisions/summary is
 * total_pnl_usd (real money — not present in the quality endpoint).
 *
 * 5-second product test the screen must pass:
 *   1. Win Rate — does the system work?
 *   2. Total PnL — does it earn?
 *   3. Profit Factor — is it stable?
 *   4. Long vs Short — where is it stronger?
 *
 * If total_trades === 0 → we DO NOT render zeros. We render the
 * "still collecting" message. Empty zero-grids look broken even when
 * the system is healthy.
 *
 * NOT TOUCHED: API endpoints, hooks, polling cadence, payload shape,
 * the cut panels' files (they remain on disk, simply un-imported).
 */

import { useDecisionAnalytics } from '../../../hooks/analytics/useDecisionAnalytics';
import { useDecisionQuality } from '../../../hooks/analytics/useDecisionQuality';

// ── Tone helpers ─────────────────────────────────────────────
function pnlTone(v) {
  const n = Number(v);
  if (!Number.isFinite(n) || n === 0) return 'text-gray-700';
  return n > 0 ? 'text-emerald-600' : 'text-red-600';
}

function winRateTone(v) {
  const n = Number(v);
  if (!Number.isFinite(n) || n === 0) return 'text-gray-700';
  return n >= 50 ? 'text-emerald-600' : 'text-red-600';
}

function profitFactorTone(v) {
  const n = Number(v);
  if (!Number.isFinite(n) || n === 0) return 'text-gray-700';
  return n >= 1.0 ? 'text-emerald-600' : 'text-red-600';
}

// ── Building blocks ──────────────────────────────────────────
function Metric({ label, value, tone = 'text-gray-900', testId }) {
  return (
    <div data-testid={testId}>
      <div className="text-sm text-gray-500">{label}</div>
      <div className={`text-2xl font-semibold tabular-nums mt-1 ${tone}`}>
        {value}
      </div>
    </div>
  );
}

function SmallMetric({ label, value, tone = 'text-gray-900' }) {
  return (
    <div>
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-sm font-semibold tabular-nums mt-0.5 ${tone}`}>
        {value}
      </div>
    </div>
  );
}

// ── Sections ─────────────────────────────────────────────────

function PerformanceSummary({ totalTrades, winRate, totalPnl, profitFactor }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5">
      <div className="text-sm font-semibold text-gray-700 mb-4">Performance</div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
        <Metric
          label="Total Trades"
          value={totalTrades}
          testId="perf-total-trades"
        />
        <Metric
          label="Win Rate"
          value={`${winRate}%`}
          tone={winRateTone(winRate)}
          testId="perf-win-rate"
        />
        <Metric
          label="Total PnL"
          value={`${totalPnl >= 0 ? '+' : ''}$${Number(totalPnl).toFixed(2)}`}
          tone={pnlTone(totalPnl)}
          testId="perf-total-pnl"
        />
        <Metric
          label="Profit Factor"
          value={Number(profitFactor).toFixed(2)}
          tone={profitFactorTone(profitFactor)}
          testId="perf-profit-factor"
        />
      </div>
    </div>
  );
}

function TradeQuality({ avgWin, avgLoss }) {
  // Render only if we actually have win/loss numbers — otherwise it's
  // visual noise on top of the "collecting outcomes" state.
  if (!Number.isFinite(avgWin) && !Number.isFinite(avgLoss)) return null;
  if (avgWin === 0 && avgLoss === 0) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5">
      <div className="text-sm font-semibold text-gray-700 mb-4">Trade Quality</div>
      <div className="grid grid-cols-2 gap-6">
        <SmallMetric
          label="Avg Win"
          value={`+$${Number(avgWin || 0).toFixed(2)}`}
          tone="text-emerald-600"
        />
        <SmallMetric
          label="Avg Loss"
          value={`-$${Math.abs(Number(avgLoss || 0)).toFixed(2)}`}
          tone="text-red-600"
        />
      </div>
    </div>
  );
}

function LongVsShort({ data }) {
  if (!data) return null;
  const long = data.LONG;
  const short = data.SHORT;
  const longHas = long && (long.trades || 0) > 0;
  const shortHas = short && (short.trades || 0) > 0;
  if (!longHas && !shortHas) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5" data-testid="long-vs-short">
      <div className="text-sm font-semibold text-gray-700 mb-4">Long vs Short</div>
      <div className="grid grid-cols-2 gap-4">
        <DirectionTile direction="Long" d={long} />
        <DirectionTile direction="Short" d={short} />
      </div>
    </div>
  );
}

function DirectionTile({ direction, d }) {
  const safe = d || { trades: 0, win_rate: 0, total_pnl: 0 };
  const tradesN = Number(safe.trades || 0);
  return (
    <div className="bg-gray-50 rounded-md p-3 space-y-1.5">
      <div className="text-xs font-semibold text-gray-700">{direction}</div>
      <div className="flex justify-between text-sm">
        <span className="text-gray-500">Trades</span>
        <span className="text-gray-900 tabular-nums">{tradesN}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-gray-500">Win rate</span>
        <span className={`tabular-nums ${winRateTone(safe.win_rate)}`}>
          {safe.win_rate}%
        </span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-gray-500">PnL</span>
        <span className={`tabular-nums ${pnlTone(safe.total_pnl)}`}>
          {Number(safe.total_pnl) >= 0 ? '+' : ''}${Number(safe.total_pnl || 0).toFixed(2)}
        </span>
      </div>
    </div>
  );
}

function ConfidenceCalibration({ data }) {
  // by_confidence: { "0.5-0.6": { trades, win_rate, avg_pnl }, ... }
  // Render only if non-empty AND has at least one bucket with trades > 0.
  if (!data || typeof data !== 'object') return null;
  const buckets = Object.entries(data).filter(
    ([, v]) => v && Number(v.trades || 0) > 0
  );
  if (buckets.length === 0) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5" data-testid="confidence-calibration">
      <div className="text-sm font-semibold text-gray-700 mb-1">Confidence vs Outcome</div>
      <div className="text-xs text-gray-500 mb-3">
        Does higher confidence really mean more wins?
      </div>
      <div className="space-y-1.5">
        {buckets.map(([bucket, v]) => (
          <div key={bucket} className="flex items-center justify-between text-sm">
            <span className="text-gray-700 font-medium">{bucket}</span>
            <div className="flex items-center gap-6 text-sm tabular-nums">
              <span className="text-gray-500">{v.trades} trades</span>
              <span className={winRateTone(v.win_rate)}>{v.win_rate}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function RecentLosses({ losses }) {
  if (!Array.isArray(losses) || losses.length === 0) return null;
  const top = losses.slice(0, 5);

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5" data-testid="recent-losses">
      <div className="text-sm font-semibold text-gray-700 mb-3">Recent losses</div>
      <div className="space-y-2">
        {top.map((l, i) => (
          <div
            key={i}
            className="flex items-center justify-between text-sm tabular-nums"
          >
            <div className="flex items-center gap-2">
              <span className="text-gray-900 font-medium">{l.symbol}</span>
              <span
                className={`text-[11px] px-1.5 py-0.5 rounded ${
                  l.side === 'LONG' || l.side === 'BUY'
                    ? 'bg-emerald-50 text-emerald-600'
                    : 'bg-red-50 text-red-600'
                }`}
              >
                {l.side === 'BUY' ? 'Long' : l.side === 'SELL' ? 'Short' : l.side}
              </span>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <span className="text-red-600">-${Math.abs(Number(l.pnl || 0)).toFixed(2)}</span>
              <span className="text-gray-400 text-xs">
                {l.timestamp
                  ? new Date(l.timestamp).toLocaleTimeString('en-GB', {
                      hour: '2-digit',
                      minute: '2-digit',
                    })
                  : '—'}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Empty state ──────────────────────────────────────────────
function EmptyState() {
  return (
    <div className="bg-white border border-gray-200 rounded-lg py-16 text-center">
      <div className="text-base font-medium text-gray-700">
        No trading data yet
      </div>
      <div className="text-sm text-gray-500 mt-1">
        Performance metrics will appear after completed trades.
      </div>
    </div>
  );
}

// ── Main ─────────────────────────────────────────────────────
export default function AnalyticsWorkspace() {
  const { data: decisionData, loading: decisionLoading } = useDecisionAnalytics();
  const { data: qualityData, loading: qualityLoading } = useDecisionQuality();

  const loading = decisionLoading || qualityLoading;

  // Single source of trading truth: decision-quality.
  // Real money number comes from decision-analytics.total_pnl_usd
  // (decision-quality doesn't expose it directly).
  const totalTrades   = Number(qualityData?.total_trades ?? 0);
  const winRate       = Number(qualityData?.win_rate ?? 0);
  const profitFactor  = Number(qualityData?.profit_factor ?? 0);
  const avgWin        = Number(qualityData?.avg_win ?? 0);
  const avgLoss       = Number(qualityData?.avg_loss ?? 0);
  const byDirection   = qualityData?.by_direction || null;
  const byConfidence  = qualityData?.by_confidence || null;
  const recentLosses  = qualityData?.recent_losses || [];
  const totalPnl      = Number(decisionData?.total_pnl_usd ?? 0);

  const hasData = totalTrades > 0;

  return (
    <div className="p-6 space-y-4" data-testid="analytics-workspace">
      {/* Header — single product framing, no R1/R2/safety subtitle */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Operational Analytics</h2>
        <p className="text-sm text-gray-500 mt-1">System performance over time</p>
      </div>

      {loading ? (
        <div className="text-sm text-gray-400 py-4">Loading analytics…</div>
      ) : !hasData ? (
        <EmptyState />
      ) : (
        <>
          <PerformanceSummary
            totalTrades={totalTrades}
            winRate={winRate}
            totalPnl={totalPnl}
            profitFactor={profitFactor}
          />

          <TradeQuality avgWin={avgWin} avgLoss={avgLoss} />

          <LongVsShort data={byDirection} />

          <ConfidenceCalibration data={byConfidence} />

          <RecentLosses losses={recentLosses} />
        </>
      )}
    </div>
  );
}
