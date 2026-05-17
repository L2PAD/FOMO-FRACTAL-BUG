/**
 * Exchange Forecast Card V2
 * ==========================
 * 
 * BLOCK E3: Production-grade forecast card for Exchange UI
 * Symmetric with SentimentForecastCard
 * 
 * Features:
 * - RAW → FINAL confidence transformation
 * - Applied multipliers display
 * - Evaluate At calculation
 * - SafeMode indicator
 * - Clean light theme
 */

import { useEffect, useState } from "react";
import { TrendingUpIcon, TrendingDownIcon, MinusIcon, ShieldAlertIcon, ShieldCheckIcon, ShieldIcon, BarChart3Icon } from "lucide-react";
import { applyExchangeAdjustments, formatPercent, getDirectionColor } from "./exchange-ui-adjustments";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const SCENARIO_CONFIG = {
  base:    { label: 'Most Likely Path',  color: 'blue',  icon: '---' },
  bullish: { label: 'Upside Scenario',   color: 'emerald', icon: '+++' },
  bearish: { label: 'Downside Risk',     color: 'red',   icon: '---' },
};

const TAG_LABELS = {
  high_confidence: { text: 'High Confidence', cls: 'bg-emerald-100 text-emerald-700' },
  moderate:        { text: 'Moderate',        cls: 'bg-blue-100 text-blue-700' },
  uncertain:       { text: 'Uncertain',       cls: 'bg-amber-100 text-amber-700' },
};

function MarketStoryBlock({ prediction, currentHorizon }) {
  const h7d = prediction?.horizons?.['7D'];
  const h30d = prediction?.horizons?.['30D'];
  const summary = prediction?.summary;
  if (!h7d && !h30d) return null;

  const shortMove = h7d?.expected_move_pct || 0;
  const longMove = h30d?.expected_move_pct || 0;
  const shortDir = shortMove > 0.1 ? 'bullish' : shortMove < -0.1 ? 'bearish' : 'neutral';
  const longDir = longMove > 0.1 ? 'bullish' : longMove < -0.1 ? 'bearish' : 'neutral';

  const divergence = (shortDir === 'bullish' && longDir === 'bearish') || (shortDir === 'bearish' && longDir === 'bullish');
  const aligned = shortDir === longDir && shortDir !== 'neutral';
  const story = marketStory(shortDir, shortMove, longDir, longMove);

  // Scenario path for 30D
  const scenarioPath = h30d?.path;
  const dominant = h30d?.dominant;
  const dominantProb = h30d?.probabilities?.[dominant] || 0;

  return (
    <div data-testid="market-story-block" className="px-5 py-3 border-t border-gray-100 bg-slate-50/70">
      {/* Market Story */}
      <div className="flex items-start gap-3 mb-2">
        <div className="flex-1">
          <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">Market Story</div>
          <div className="flex items-center gap-4 text-xs">
            <span>
              Short-term: <span className={`font-semibold ${shortDir === 'bullish' ? 'text-emerald-600' : shortDir === 'bearish' ? 'text-red-600' : 'text-gray-500'}`}>
                {shortDir} ({shortMove >= 0 ? '+' : ''}{shortMove.toFixed(1)}%)
              </span>
            </span>
            <span>
              Long-term: <span className={`font-semibold ${longDir === 'bullish' ? 'text-emerald-600' : longDir === 'bearish' ? 'text-red-600' : 'text-gray-500'}`}>
                {longDir} ({longMove >= 0 ? '+' : ''}{longMove.toFixed(1)}%)
              </span>
            </span>
          </div>
          <div className="text-xs text-gray-600 mt-1 italic" data-testid="story-interpretation">
            → {story}
          </div>
        </div>
      </div>

      {/* Divergence + Scenario row */}
      <div className="flex items-center gap-4 mt-1">
        {/* Divergence */}
        <span data-testid="divergence-label"
          className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
            divergence ? 'bg-amber-100 text-amber-700' : aligned ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'
          }`}
        >
          {divergence ? '⚠️ Divergence detected' : aligned ? '✓ Aligned' : 'Mixed'}
        </span>

        {/* Agreement */}
        {summary?.horizon_agreement != null && (
          <span className="text-[10px] text-gray-500">
            Agreement: <span className="font-semibold text-gray-700">{Math.round(summary.horizon_agreement * 100)}%</span>
          </span>
        )}

        {/* Scenario path */}
        {(scenarioPath || dominantProb > 0) && (
          <span data-testid="scenario-path" className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
            dominantProb < 0.4 ? 'bg-amber-50 text-amber-600' : 'bg-gray-100 text-gray-600'
          }`}>
            Scenario: {dominantProb >= 0.4
              ? <>{scenarioPath?.replace(/_/g, ' ') || dominant} ({Math.round(dominantProb * 100)}%)</>
              : <span className="text-amber-600">uncertain</span>
            }
          </span>
        )}
      </div>
    </div>
  );
}

function ScenarioPanel({ scenarios }) {
  if (!scenarios?.scenarios?.length) return null;

  const sorted = [...scenarios.scenarios].sort((a, b) => {
    const order = { base: 0, bullish: 1, bearish: 2 };
    return (order[a.type] ?? 3) - (order[b.type] ?? 3);
  });

  const tag = TAG_LABELS[scenarios.confidence_tag] || TAG_LABELS.uncertain;

  return (
    <div data-testid="scenario-panel" className="border-t border-gray-100">
      <div className="px-5 pt-3 pb-1 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3Icon className="w-3.5 h-3.5 text-gray-400" />
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            30D Scenarios
          </span>
        </div>
        <span data-testid="scenario-confidence-tag" className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${tag.cls}`}>
          {tag.text}
        </span>
      </div>

      <div className="px-5 pb-3 space-y-1.5">
        {sorted.map((s) => {
          const cfg = SCENARIO_CONFIG[s.type] || SCENARIO_CONFIG.base;
          const probPct = Math.round(s.probability * 100);
          const isBase = s.type === 'base';
          const isDominant = s.type === scenarios.dominant;

          return (
            <div
              key={s.type}
              data-testid={`scenario-row-${s.type}`}
              className={`flex items-center gap-3 py-1.5 px-3 rounded-lg transition-colors ${
                isDominant ? 'bg-gray-50' : ''
              }`}
            >
              {/* Probability bar */}
              <div className="w-10 text-right">
                <span className={`text-xs font-bold ${
                  cfg.color === 'emerald' ? 'text-emerald-600'
                    : cfg.color === 'red' ? 'text-red-600'
                    : 'text-blue-600'
                }`}>
                  {probPct}%
                </span>
              </div>

              {/* Visual bar */}
              <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    cfg.color === 'emerald' ? 'bg-emerald-400'
                      : cfg.color === 'red' ? 'bg-red-400'
                      : 'bg-blue-400'
                  }`}
                  style={{ width: `${Math.min(probPct * 2, 100)}%` }}
                />
              </div>

              {/* Label */}
              <div className="flex-1 min-w-0">
                <span className={`text-xs ${isBase ? 'font-semibold text-gray-700' : 'text-gray-600'}`}>
                  {cfg.label}
                </span>
                {isDominant && (
                  <span className="ml-1.5 text-[9px] font-bold text-gray-400 uppercase">
                    primary
                  </span>
                )}
              </div>

              {/* Range */}
              <div className="text-right whitespace-nowrap">
                <span className={`text-[11px] font-mono ${
                  cfg.color === 'emerald' ? 'text-emerald-600'
                    : cfg.color === 'red' ? 'text-red-600'
                    : 'text-gray-600'
                }`}>
                  {s.range[0] > 0 ? '+' : ''}{s.range[0].toFixed(1)}% / {s.range[1] > 0 ? '+' : ''}{s.range[1].toFixed(1)}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// --- Interpretation helpers ---
function strengthLabel(confidence) {
  if (confidence >= 0.6) return 'strong';
  if (confidence >= 0.35) return 'moderate';
  return 'weak';
}

function marketStory(shortDir, shortMove, longDir, longMove) {
  const sUp = shortMove > 0.1;
  const sDown = shortMove < -0.1;
  const lUp = longMove > 0.1;
  const lDown = longMove < -0.1;

  if (sUp && lDown) return 'bounce inside downtrend';
  if (sDown && lUp) return 'pullback in uptrend';
  if (sUp && lUp) return 'trend continuation (bullish)';
  if (sDown && lDown) return 'trend continuation (bearish)';
  return 'range-bound / consolidation';
}

export default function ExchangeForecastCardV2({ symbol = 'BTC', horizon = '7D' }) {
  const [data, setData] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch(`${API_URL}/api/market/chart/exchange-v2?symbol=${symbol}&horizon=${horizon}`).then(r => r.json()).catch(() => null),
      fetch(`${API_URL}/api/forecast/prediction/${symbol}`).then(r => r.json()).catch(() => null),
    ]).then(([cardData, predData]) => {
      if (cardData) setData(cardData);
      if (predData?.ok) setPrediction(predData);
      setLoading(false);
    });
  }, [symbol, horizon]);

  if (loading || !data) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-1/3 mb-4" />
        <div className="h-8 bg-gray-200 rounded w-1/2 mb-2" />
        <div className="h-4 bg-gray-200 rounded w-2/3" />
      </div>
    );
  }

  const adjusted = applyExchangeAdjustments(data);
  const { forecast, reliability, meta, explain, uncertainty, executionStatus, scenarios } = data;
  const direction = forecast?.direction || 'NEUTRAL';
  const directionColor = getDirectionColor(direction);

  const entry = forecast?.entry || 0;
  const targetRaw = forecast?.targetRaw || entry;
  const targetFinal = forecast?.targetFinal || entry;
  const expectedMovePct = forecast?.expectedMovePct || 0;
  const evaluateAt = forecast?.evaluateAt ? new Date(forecast.evaluateAt).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }) : '—';

  const rawConfidence = reliability?.rawConfidence || 0;
  const finalConfidence = adjusted?.confidenceFinal || 0;

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
        <span className="text-sm font-medium text-gray-600" data-testid="exchange-card-title">Exchange</span>
        {direction === 'LONG' || direction === 'BULLISH'
          ? <TrendingUpIcon className="w-4 h-4 text-emerald-600" />
          : direction === 'SHORT' || direction === 'BEARISH'
            ? <TrendingDownIcon className="w-4 h-4 text-red-600" />
            : <MinusIcon className="w-4 h-4 text-gray-400" />
        }
        <span
          className={`text-sm font-bold ${
            direction === 'LONG' || direction === 'BULLISH'
              ? 'text-emerald-600'
              : direction === 'SHORT' || direction === 'BEARISH'
                ? 'text-red-600'
                : 'text-gray-500'
          }`}
          data-testid="exchange-card-direction"
        >
          {direction === 'LONG' || direction === 'BULLISH' ? 'Bullish'
            : direction === 'SHORT' || direction === 'BEARISH' ? 'Bearish'
            : 'HOLD'}
        </span>
        <span className="text-sm font-medium text-gray-500" data-testid="exchange-card-confidence">
          {Math.round(finalConfidence * 100)}%
        </span>

        {/* Uncertainty Badge */}
        {uncertainty && (
          <span
            data-testid="uncertainty-badge"
            className={`ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold tracking-wide ${
              uncertainty.level === 'low'
                ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
                : uncertainty.level === 'mid'
                  ? 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'
                  : 'bg-red-50 text-red-700 ring-1 ring-red-200'
            }`}
          >
            {uncertainty.level === 'low'
              ? <ShieldCheckIcon className="w-3.5 h-3.5" />
              : uncertainty.level === 'mid'
                ? <ShieldIcon className="w-3.5 h-3.5" />
                : <ShieldAlertIcon className="w-3.5 h-3.5" />
            }
            {uncertainty.level === 'low' ? 'CONFIDENT'
              : uncertainty.level === 'mid' ? 'UNCERTAIN'
              : 'LOW CONFIDENCE'}
          </span>
        )}
      </div>

      {/* High Uncertainty Warning Banner */}
      {uncertainty?.level === 'high' && (
        <div
          data-testid="uncertainty-warning-banner"
          className="px-5 py-3 bg-red-50 border-b border-red-100 flex items-center gap-3"
        >
          <ShieldAlertIcon className="w-4 h-4 text-red-500 flex-shrink-0" />
          <div className="text-xs text-red-700">
            <span className="font-semibold">Low confidence environment</span>
            <span className="text-red-500 ml-1.5">
              {uncertainty.dominantRegime === 'transition' && '— market in transition, historically 8% accuracy'}
              {uncertainty.dominantRegime === 'trend' && '— weak trend conviction'}
              {uncertainty.dominantRegime === 'range' && '— range-bound, low directional edge'}
              {!['transition', 'trend', 'range'].includes(uncertainty.dominantRegime) && `— ${uncertainty.dominantRegime} regime`}
            </span>
          </div>
        </div>
      )}

      {/* Main content */}
      <div className="p-5 grid grid-cols-3 gap-6">
        {/* Expected Move (PRIMARY signal) */}
        <div data-testid="expected-move-block">
          <div className="text-xs text-gray-500 mb-1">Expected Move</div>
          <div 
            className="text-2xl font-semibold"
            style={{ color: expectedMovePct > 0.001 ? '#16a34a' : expectedMovePct < -0.001 ? '#dc2626' : '#64748b' }}
          >
            {expectedMovePct >= 0 ? '+' : ''}{formatPercent(expectedMovePct)}
          </div>
          {/* Direction label with strength */}
          <div className="mt-1">
            <span 
              data-testid="direction-label"
              className="text-xs font-semibold uppercase tracking-wide"
              style={{ color: expectedMovePct > 0.001 ? '#16a34a' : expectedMovePct < -0.001 ? '#dc2626' : '#64748b' }}
            >
              {expectedMovePct > 0.001 ? 'BULLISH' : expectedMovePct < -0.001 ? 'BEARISH' : 'NEUTRAL'}
              {' '}({strengthLabel(finalConfidence)})
            </span>
          </div>
          {/* Target secondary */}
          <div className="text-xs text-gray-400 mt-1.5" data-testid="target-secondary">
            Target: ${targetFinal.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            <span className="text-gray-300 ml-1">(derived)</span>
          </div>
        </div>

        {/* Confidence */}
        <div>
          <div className="text-xs text-gray-500 mb-1">Confidence</div>
          <div className="text-2xl font-semibold text-gray-900">
            {Math.round(finalConfidence * 100)}%
          </div>
          {finalConfidence !== rawConfidence && (
            <div className="text-xs text-gray-400 mt-1">
              RAW: {Math.round(rawConfidence * 100)}%
            </div>
          )}
          {/* Uncertainty context */}
          {uncertainty && (
            <div
              data-testid="uncertainty-context"
              className={`text-xs mt-1.5 font-medium ${
                uncertainty.level === 'low' ? 'text-emerald-600'
                  : uncertainty.level === 'mid' ? 'text-amber-600'
                  : 'text-red-600'
              }`}
            >
              Uncertainty: {uncertainty.level.toUpperCase()} ({(uncertainty.value * 100).toFixed(0)}%)
            </div>
          )}
        </div>

        {/* 30D Range or Evaluate At */}
        <div>
          {prediction?.horizons?.['30D']?.scenario_details && horizon === '30D' ? (
            <div data-testid="range-block">
              <div className="text-xs text-gray-500 mb-1">30D Range</div>
              {(() => {
                const details = prediction.horizons['30D'].scenario_details;
                const allPrices = details.flatMap(s => [s.target_low, s.target_high]).filter(Boolean);
                const minP = allPrices.length ? Math.min(...allPrices) : 0;
                const maxP = allPrices.length ? Math.max(...allPrices) : 0;
                return (
                  <>
                    <div className="text-sm font-semibold text-gray-900">
                      ${minP.toLocaleString(undefined, { maximumFractionDigits: 0 })} — ${maxP.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      Scenario range (bull/bear)
                    </div>
                  </>
                );
              })()}
              <div className="text-xs text-gray-400 mt-1">
                Horizon: {horizon}
              </div>
            </div>
          ) : (
            <div>
              <div className="text-xs text-gray-500 mb-1">Evaluate At</div>
              <div className="text-sm font-medium text-gray-900 mt-1">
                {evaluateAt}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                Horizon: {horizon}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Market Story + Divergence (from prediction API) */}
      {prediction?.horizons && (
        <MarketStoryBlock prediction={prediction} currentHorizon={horizon} />
      )}

      {/* Execution Status Panel */}
      {executionStatus && (
        <div
          data-testid="execution-status-panel"
          className={`px-5 py-3 border-t flex items-center justify-between ${
            executionStatus.mode === 'normal'
              ? 'bg-emerald-50 border-emerald-100'
              : executionStatus.mode === 'reduced'
                ? 'bg-amber-50 border-amber-100'
                : 'bg-red-50 border-red-100'
          }`}
        >
          <div className="flex items-center gap-3">
            <div className={`w-2 h-2 rounded-full ${
              executionStatus.mode === 'normal' ? 'bg-emerald-500'
                : executionStatus.mode === 'reduced' ? 'bg-amber-500'
                : 'bg-red-500'
            }`} />
            <div>
              <span
                data-testid="execution-mode"
                className={`text-xs font-semibold uppercase tracking-wide ${
                  executionStatus.mode === 'normal' ? 'text-emerald-700'
                    : executionStatus.mode === 'reduced' ? 'text-amber-700'
                    : 'text-red-700'
                }`}
              >
                Execution: {executionStatus.mode}
              </span>
              <span className="text-xs text-gray-500 ml-2">
                {executionStatus.reason}
              </span>
            </div>
          </div>
          <div className="text-right">
            <span
              data-testid="execution-size-factor"
              className={`text-sm font-bold ${
                executionStatus.mode === 'normal' ? 'text-emerald-700'
                  : executionStatus.mode === 'reduced' ? 'text-amber-700'
                  : 'text-red-700'
              }`}
            >
              Size: {executionStatus.sizeFactor}x
            </span>
          </div>
        </div>
      )}

      {/* Scenario Decision Panel (30D only) */}
      {scenarios && scenarios.scenarios && (
        <ScenarioPanel scenarios={scenarios} />
      )}

      {/* Multipliers footer */}
      <div className="px-5 py-3 bg-gray-50 border-t border-gray-100">
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span>Applied Multipliers:</span>
          <span className={reliability?.uriMultiplier !== 1 ? 'text-blue-600 font-medium' : ''}>
            URI x{reliability?.uriMultiplier?.toFixed(2) || '1.00'}
          </span>
          <span className={reliability?.calibrationMultiplier !== 1 ? 'text-purple-600 font-medium' : ''}>
            Calib x{reliability?.calibrationMultiplier?.toFixed(2) || '1.00'}
          </span>
          <span className={reliability?.capitalMultiplier !== 1 ? 'text-violet-600 font-medium' : ''}>
            Capital x{reliability?.capitalMultiplier?.toFixed(2) || '1.00'}
          </span>
          {uncertainty && (
            <span className="ml-auto text-gray-400" data-testid="regime-label">
              Regime: <span className="font-medium text-gray-600">{uncertainty.dominantRegime}</span>
            </span>
          )}
        </div>
      </div>

      {/* Explain block (if available) */}
      {explain && (
        <div className="px-5 py-3 bg-gray-50 border-t border-gray-100">
          <div className="text-xs text-gray-500">
            <span className="font-medium">Formula: </span>
            {explain.adjustments?.rawConfidence?.toFixed(2) || rawConfidence.toFixed(2)} × 
            {reliability?.uriMultiplier?.toFixed(2) || '1.00'} × 
            {reliability?.calibrationMultiplier?.toFixed(2) || '1.00'} × 
            {reliability?.capitalMultiplier?.toFixed(2) || '1.00'} = 
            <span className="font-medium ml-1">{finalConfidence.toFixed(2)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
