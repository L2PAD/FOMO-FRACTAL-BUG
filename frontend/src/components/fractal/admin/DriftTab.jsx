/**
 * Вкладка Drift — анализ отклонения модели
 * 
 * Показывает сравнение текущих метрик с историческими базовыми линиями.
 * Включает P6 метрики: by-horizon, rolling trend, regime segmentation.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

// ═══════════════════════════════════════════════════════════════
// SEVERITY & CONFIDENCE BADGES
// ═══════════════════════════════════════════════════════════════

const severityLabels = {
  OK: 'Норма',
  WATCH: 'Наблюдение',
  WARN: 'Внимание',
  CRITICAL: 'Критично',
};

const confidenceLabels = {
  LOW: 'Низкая',
  MED: 'Средняя',
  HIGH: 'Высокая',
};

function SeverityBadge({ severity, size = 'md' }) {
  const colors = {
    OK: 'bg-emerald-100 text-emerald-800 border-emerald-400',
    WATCH: 'bg-sky-100 text-sky-800 border-sky-400',
    WARN: 'bg-amber-100 text-amber-800 border-amber-400',
    CRITICAL: 'bg-red-100 text-red-800 border-red-400',
  };
  
  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-5 py-2 text-lg font-bold',
  };
  
  return (
    <span 
      className={`rounded-lg border-2 ${colors[severity] || colors.WATCH} ${sizes[size]}`} 
      data-testid={`severity-badge-${severity}`}
      title={`Уровень серьёзности: ${severityLabels[severity] || severity}`}
    >
      {severityLabels[severity] || severity}
    </span>
  );
}

function ConfidenceBadge({ confidence }) {
  const colors = {
    LOW: 'bg-gray-100 text-gray-600 border-gray-300',
    MED: 'bg-blue-50 text-blue-700 border-blue-300',
    HIGH: 'bg-green-50 text-green-700 border-green-300',
  };
  
  return (
    <span 
      className={`px-3 py-1 text-sm rounded-lg border ${colors[confidence] || colors.LOW}`} 
      data-testid="confidence-badge"
      title="Уровень уверенности в оценке"
    >
      Уверенность: {confidenceLabels[confidence] || confidence}
    </span>
  );
}

// ═══════════════════════════════════════════════════════════════
// DRIFT HEADER (Verdict Bar)
// ═══════════════════════════════════════════════════════════════

function DriftHeader({ verdict, meta, windowDays, onWindowChange }) {
  const windows = [30, 60, 90, 180, 365];
  
  return (
    <div className="bg-slate-900 rounded-xl p-6" data-testid="drift-header">
      <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
        <div>
          <h2 className="text-2xl font-bold text-white mb-1">Анализ Drift</h2>
          <p className="text-slate-400 text-sm">Сравнение текущих метрик с историческими данными</p>
        </div>
        
        <div className="flex items-center gap-3">
          <SeverityBadge severity={verdict?.severity || 'WATCH'} size="lg" />
          <ConfidenceBadge confidence={verdict?.confidence || 'LOW'} />
        </div>
      </div>
      
      {/* Window Selector */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-slate-400 text-sm" title="Период анализа данных">Период:</span>
        {windows.map(w => (
          <button
            key={w}
            onClick={() => onWindowChange(w)}
            className={`px-3 py-1 text-sm rounded-lg transition-colors ${
              windowDays === w
                ? 'bg-blue-600 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
            data-testid={`window-btn-${w}`}
            title={`Анализ за последние ${w} дней`}
          >
            {w}д
          </button>
        ))}
      </div>
      
      {/* Reasons Chips */}
      {verdict?.reasons && verdict.reasons.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {verdict.reasons.map((reason, i) => (
            <span key={i} className="px-3 py-1 bg-slate-700 text-slate-300 text-xs rounded-full">
              {reason}
            </span>
          ))}
        </div>
      )}
      
      {/* Insufficient LIVE Truth Warning */}
      {verdict?.insufficientLiveTruth && (
        <div className="bg-amber-900/30 border border-amber-500/50 rounded-lg p-3 mb-4">
          <div className="flex items-center gap-2 text-amber-400">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span className="font-medium">Недостаточно реальных данных (&lt;30)</span>
          </div>
          <p className="text-amber-300 text-sm mt-1">
            Метрики drift основаны на тестовых данных. Применение изменений заблокировано до накопления ≥30 реальных результатов.
          </p>
        </div>
      )}
      
      {/* Sample Counts */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-slate-800 rounded-lg p-3">
          <div className="text-xs text-slate-400 mb-1" title="Количество реальных прогнозов с результатами">Реальные данные</div>
          <div className={`text-2xl font-bold ${meta?.liveSamples > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {(meta?.liveSamples || 0).toLocaleString()}
          </div>
          <div className="text-xs text-slate-500">
            {meta?.liveSamples >= 30 ? 'Достаточно' : `Нужно ещё ${30 - (meta?.liveSamples || 0)}`}
          </div>
        </div>
        <div className="bg-slate-800 rounded-lg p-3">
          <div className="text-xs text-slate-400 mb-1" title="Исторические данные с 2020 года">V2020</div>
          <div className="text-2xl font-bold text-blue-400">
            {(meta?.v2020Samples || 0).toLocaleString()}
          </div>
          <div className="text-xs text-slate-500">Современная история</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-3">
          <div className="text-xs text-slate-400 mb-1" title="Исторические данные с 2014 года">V2014</div>
          <div className="text-2xl font-bold text-purple-400">
            {(meta?.v2014Samples || 0).toLocaleString()}
          </div>
          <div className="text-xs text-slate-500">Vintage Historical</div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// COHORT SNAPSHOT CARDS
// ═══════════════════════════════════════════════════════════════

function CohortCard({ cohort, isPrimary }) {
  const cohortColors = {
    LIVE: 'border-emerald-500 bg-emerald-500/10',
    V2020: 'border-blue-500 bg-blue-500/10',
    V2014: 'border-purple-500 bg-purple-500/10',
  };
  
  const metrics = cohort?.metrics || {};
  
  const formatPct = (val) => val !== undefined ? `${(val * 100).toFixed(1)}%` : '—';
  const formatNum = (val, decimals = 2) => val !== undefined ? val.toFixed(decimals) : '—';
  
  return (
    <div className={`rounded-xl border-2 p-4 ${cohortColors[cohort?.cohortId] || 'border-gray-300'}`} data-testid={`cohort-card-${cohort?.cohortId}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="font-bold text-lg">{cohort?.cohortId}</span>
          {isPrimary && (
            <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs rounded">Primary</span>
          )}
        </div>
        <span className="text-gray-500 text-sm">{metrics.samples?.toLocaleString() || 0} samples</span>
      </div>
      
      <div className="grid grid-cols-2 gap-2">
        <MetricCell label="Hit Rate" value={formatPct(metrics.hitRate)} />
        <MetricCell label="Sharpe" value={formatNum(metrics.sharpe)} />
        <MetricCell label="Expectancy" value={formatPct(metrics.expectancy)} />
        <MetricCell label="Max DD" value={formatPct(metrics.maxDD)} />
        <MetricCell label="Profit Factor" value={formatNum(metrics.profitFactor)} />
        <MetricCell label="Calibration Err" value={formatPct(metrics.calibrationError)} />
      </div>
      
      {/* Coverage */}
      {cohort?.coverage && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <div className="text-xs text-gray-500 mb-1">Coverage</div>
          <div className="flex flex-wrap gap-1">
            {cohort.coverage.horizons?.slice(0, 4).map(h => (
              <span key={h} className="px-1.5 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">{h}</span>
            ))}
            {cohort.coverage.regimes?.slice(0, 3).map(r => (
              <span key={r} className="px-1.5 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">{r}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCell({ label, value }) {
  return (
    <div className="bg-white/50 rounded p-2">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="font-semibold text-gray-900">{value}</div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// DELTA MATRIX
// ═══════════════════════════════════════════════════════════════

function DeltaMatrix({ deltas }) {
  const pairs = [
    { key: 'LIVE_vs_V2020', label: 'LIVE → V2020', subtitle: 'vs Modern Baseline' },
    { key: 'LIVE_vs_V2014', label: 'LIVE → V2014', subtitle: 'vs Vintage Baseline' },
    { key: 'V2020_vs_V2014', label: 'V2020 → V2014', subtitle: 'Baseline Gap' },
  ];
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="delta-matrix">
      <h3 className="font-bold text-gray-900 mb-4">Delta Matrix (Cohort Comparisons)</h3>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 px-3 font-medium text-gray-600">Comparison</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600">Δ HitRate</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600">Δ Sharpe</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600">Δ Calibration</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600">Δ MaxDD</th>
            </tr>
          </thead>
          <tbody>
            {pairs.map(({ key, label, subtitle }) => {
              const d = deltas?.[key];
              return (
                <tr key={key} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-3 px-3">
                    <div className="font-medium">{label}</div>
                    <div className="text-xs text-gray-500">{subtitle}</div>
                  </td>
                  <DeltaCell value={d?.dHitRate_pp} suffix="pp" />
                  <DeltaCell value={d?.dSharpe} />
                  <DeltaCell value={d?.dCalibration_pp} suffix="pp" />
                  <DeltaCell value={d?.dMaxDD_pp} suffix="pp" inverted />
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DeltaCell({ value, suffix = '', inverted = false }) {
  if (value === undefined || value === null) {
    return <td className="py-3 px-3 text-center text-gray-400">—</td>;
  }
  
  const absVal = Math.abs(value);
  let colorClass = 'text-gray-700';
  
  // For most metrics: positive = good (green), negative = bad (red)
  // For MaxDD: positive = worse (red), negative = better (green)
  const isGood = inverted ? value < 0 : value > 0;
  const isBad = inverted ? value > 0 : value < 0;
  
  if (absVal >= 5) {
    colorClass = isGood ? 'text-emerald-600 font-bold' : 'text-red-600 font-bold';
  } else if (absVal >= 2) {
    colorClass = isGood ? 'text-emerald-600' : 'text-red-500';
  }
  
  const sign = value > 0 ? '+' : '';
  
  return (
    <td className={`py-3 px-3 text-center ${colorClass}`}>
      {sign}{value.toFixed(2)}{suffix}
    </td>
  );
}

// ═══════════════════════════════════════════════════════════════
// SEVERITY LADDER (Rule Explainer)
// ═══════════════════════════════════════════════════════════════

function SeverityLadder({ thresholds }) {
  return (
    <div className="bg-slate-50 rounded-xl border border-slate-200 p-4" data-testid="severity-ladder">
      <h3 className="font-bold text-gray-900 mb-3">Severity Thresholds (Deterministic)</h3>
      
      <div className="space-y-2 text-sm">
        <div className="flex items-center gap-2">
          <SeverityBadge severity="CRITICAL" size="sm" />
          <span className="text-gray-600">
            |ΔHit| ≥ {thresholds?.CRITICAL?.hitRate_pp || 8}pp OR |ΔSharpe| ≥ {thresholds?.CRITICAL?.sharpe || 0.8} OR |ΔCalib| ≥ {thresholds?.CRITICAL?.calibration_pp || 8}pp
          </span>
        </div>
        <div className="flex items-center gap-2">
          <SeverityBadge severity="WARN" size="sm" />
          <span className="text-gray-600">
            |ΔHit| ≥ {thresholds?.WARN?.hitRate_pp || 5}pp OR |ΔSharpe| ≥ {thresholds?.WARN?.sharpe || 0.5} OR |ΔCalib| ≥ {thresholds?.WARN?.calibration_pp || 5}pp
          </span>
        </div>
        <div className="flex items-center gap-2">
          <SeverityBadge severity="WATCH" size="sm" />
          <span className="text-gray-600">
            |ΔHit| ≥ {thresholds?.WATCH?.hitRate_pp || 2}pp OR |ΔSharpe| ≥ {thresholds?.WATCH?.sharpe || 0.2} OR |ΔCalib| ≥ {thresholds?.WATCH?.calibration_pp || 2}pp
          </span>
        </div>
        <div className="flex items-center gap-2">
          <SeverityBadge severity="OK" size="sm" />
          <span className="text-gray-600">All metrics within acceptable bounds</span>
        </div>
        
        <div className="mt-2 pt-2 border-t border-slate-200 text-xs text-gray-500">
          <strong>Confidence Gating:</strong> LIVE &lt;30 → LOW, 30-89 → MED, ≥90 → HIGH. LOW confidence caps severity at WATCH.
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// ACTIONS PANEL
// ═══════════════════════════════════════════════════════════════

function ActionsPanel({ verdict, onAction }) {
  const actions = verdict?.recommendedActions || [];
  
  const actionLabels = {
    NO_ACTION_REQUIRED: { label: 'No Action Required', color: 'bg-gray-100 text-gray-700' },
    CONTINUE_MONITORING: { label: 'Continue Monitoring', color: 'bg-blue-100 text-blue-700' },
    ACCUMULATE_LIVE_DATA: { label: 'Accumulate LIVE Data', color: 'bg-amber-100 text-amber-700' },
    FREEZE_POLICY_CHANGES: { label: 'Freeze Policy Changes', color: 'bg-red-100 text-red-700' },
    INVESTIGATE_ROOT_CAUSE: { label: 'Investigate Root Cause', color: 'bg-red-100 text-red-700' },
    INVESTIGATE_DRIFT_SOURCE: { label: 'Investigate Drift Source', color: 'bg-amber-100 text-amber-700' },
    REVIEW_TIER_WEIGHTS: { label: 'Review Tier Weights', color: 'bg-amber-100 text-amber-700' },
    MONITOR_NEXT_7_DAYS: { label: 'Monitor Next 7 Days', color: 'bg-blue-100 text-blue-700' },
  };
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="actions-panel">
      <h3 className="font-bold text-gray-900 mb-3">Recommended Actions</h3>
      
      <div className="flex flex-wrap gap-2">
        {actions.map((action, i) => {
          const config = actionLabels[action] || { label: action, color: 'bg-gray-100 text-gray-700' };
          return (
            <span key={i} className={`px-3 py-1.5 rounded-lg text-sm font-medium ${config.color}`}>
              {config.label}
            </span>
          );
        })}
      </div>
      
      {/* Quick Action Buttons */}
      <div className="flex gap-2 mt-4 pt-4 border-t border-gray-200">
        <button
          onClick={() => onAction('openGovernance')}
          className="px-4 py-2 bg-slate-100 text-slate-700 text-sm rounded-lg hover:bg-slate-200 transition-colors"
          data-testid="action-governance"
        >
          Open Governance Tab
        </button>
        <button
          onClick={() => onAction('openOps')}
          className="px-4 py-2 bg-slate-100 text-slate-700 text-sm rounded-lg hover:bg-slate-200 transition-colors"
          data-testid="action-ops"
        >
          Open Ops Tab
        </button>
        <button
          onClick={() => onAction('writeSnapshot')}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
          data-testid="action-snapshot"
        >
          Write Snapshot Now
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// BREAKDOWN TABLES
// ═══════════════════════════════════════════════════════════════

function BreakdownSection({ breakdowns }) {
  const [activeBreakdown, setActiveBreakdown] = useState('byTier');
  
  const tabs = [
    { id: 'byTier', label: 'By Tier' },
    { id: 'byRegime', label: 'By Regime' },
    { id: 'byDivergence', label: 'By Divergence' },
  ];
  
  const data = breakdowns?.[activeBreakdown] || [];
  const labelKey = activeBreakdown === 'byTier' ? 'tier' : activeBreakdown === 'byRegime' ? 'regime' : 'grade';
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="breakdown-section">
      <h3 className="font-bold text-gray-900 mb-3">Drift Breakdown</h3>
      
      {/* Tabs */}
      <div className="flex gap-2 mb-4">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveBreakdown(tab.id)}
            className={`px-4 py-2 text-sm rounded-lg transition-colors ${
              activeBreakdown === tab.id
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
            data-testid={`breakdown-tab-${tab.id}`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      
      {/* Table */}
      {data.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-2 px-3 font-medium text-gray-600">Value</th>
                <th className="text-center py-2 px-3 font-medium text-gray-600">Severity</th>
                <th className="text-center py-2 px-3 font-medium text-gray-600">LIVE Samples</th>
                <th className="text-center py-2 px-3 font-medium text-gray-600">Δ Hit (vs V2020)</th>
                <th className="text-center py-2 px-3 font-medium text-gray-600">Δ Sharpe</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row, i) => (
                <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-2 px-3 font-medium">{row[labelKey] || 'UNKNOWN'}</td>
                  <td className="py-2 px-3 text-center">
                    <SeverityBadge severity={row.worstSeverity} size="sm" />
                  </td>
                  <td className="py-2 px-3 text-center">{row.live?.samples || 0}</td>
                  <DeltaCell value={row.delta_LIVE_V2020?.dHitRate_pp} suffix="pp" />
                  <DeltaCell value={row.delta_LIVE_V2020?.dSharpe} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-gray-500 text-sm py-4 text-center">No breakdown data available</div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// P6-A: BY-HORIZON TABLE
// ═══════════════════════════════════════════════════════════════

function ByHorizonTable({ byHorizon, dataMode }) {
  if (!byHorizon || byHorizon.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h3 className="font-bold text-gray-900 mb-3">Метрики по горизонтам</h3>
        <div className="text-gray-500 text-sm py-4 text-center">Нет данных по горизонтам</div>
      </div>
    );
  }
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="by-horizon-table">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-bold text-gray-900" title="Качество прогнозов для разных горизонтов прогнозирования">Метрики по горизонтам</h3>
        <span className={`px-2 py-1 text-xs rounded ${dataMode === 'SEED' ? 'bg-amber-100 text-amber-800' : 'bg-green-100 text-green-800'}`}>
          {dataMode === 'SEED' ? 'Тест. данные' : dataMode === 'LIVE' ? 'Реальные' : dataMode}
        </span>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 px-3 font-medium text-gray-600" title="Горизонт прогноза в днях">Горизонт</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600" title="Количество завершённых прогнозов">Выборка</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600" title="Процент успешных прогнозов">Точность</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600" title="Средняя абсолютная ошибка">Ср. ошибка</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600" title="Медианная ошибка">P50</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600" title="90-й перцентиль ошибки">P90</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600" title="Максимальная ошибка">Max</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600" title="Направление изменения качества">Тренд</th>
            </tr>
          </thead>
          <tbody>
            {byHorizon.map((h, i) => (
              <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-2 px-3 font-medium">{h.horizon}</td>
                <td className="py-2 px-3 text-center">{h.sampleCount}</td>
                <td className="py-2 px-3 text-center font-mono">
                  <span className={h.hitRate >= 55 ? 'text-green-600' : h.hitRate >= 50 ? 'text-yellow-600' : 'text-red-600'}>
                    {h.hitRate}%
                  </span>
                </td>
                <td className="py-2 px-3 text-center font-mono">{h.avgAbsError}%</td>
                <td className="py-2 px-3 text-center font-mono text-gray-600">{h.p50}%</td>
                <td className="py-2 px-3 text-center font-mono text-gray-600">{h.p90}%</td>
                <td className="py-2 px-3 text-center font-mono text-gray-600">{h.max}%</td>
                <td className="py-2 px-3 text-center">
                  <span className={`px-2 py-1 text-xs rounded ${
                    h.trend === 'improving' ? 'bg-green-100 text-green-800' :
                    h.trend === 'worsening' ? 'bg-red-100 text-red-800' :
                    'bg-gray-100 text-gray-600'
                  }`}>
                    {h.trend === 'improving' ? 'Улучшается' : h.trend === 'worsening' ? 'Ухудшается' : 'Стабильно'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// P6-B: ROLLING TREND
// ═══════════════════════════════════════════════════════════════

function RollingTrend({ points }) {
  if (!points || points.length === 0) {
    return null;
  }
  
  // Show last 5 windows
  const lastPoints = points.slice(-5);
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="rolling-trend">
      <h3 className="font-bold text-gray-900 mb-3" title="Динамика метрик за последние 5 окон расчёта">Динамика по окнам</h3>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 px-3 font-medium text-gray-600">Конец окна</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600">Точность</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600">Ср. ошибка</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600">Выборка</th>
            </tr>
          </thead>
          <tbody>
            {lastPoints.map((p, i) => (
              <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-2 px-3 font-mono text-gray-600">{p.windowEnd}</td>
                <td className="py-2 px-3 text-center font-mono">
                  <span className={p.hitRate >= 55 ? 'text-green-600' : p.hitRate >= 50 ? 'text-yellow-600' : 'text-red-600'}>
                    {p.hitRate}%
                  </span>
                </td>
                <td className="py-2 px-3 text-center font-mono">{p.avgAbsError}%</td>
                <td className="py-2 px-3 text-center">{p.sampleCount}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// P6-C: BY-REGIME TABLE
// ═══════════════════════════════════════════════════════════════

const regimeLabels = {
  BULL_LOW_VOL: 'Рост, низкая волатильность',
  BULL_HIGH_VOL: 'Рост, высокая волатильность',
  BEAR_LOW_VOL: 'Падение, низкая волатильность',
  BEAR_HIGH_VOL: 'Падение, высокая волатильность',
  UNKNOWN: 'Неопределённый',
};

function ByRegimeTable({ byRegime }) {
  if (!byRegime || byRegime.length === 0) {
    return null;
  }
  
  const regimeColors = {
    BULL_LOW_VOL: 'bg-green-50',
    BULL_HIGH_VOL: 'bg-green-100',
    BEAR_LOW_VOL: 'bg-red-50',
    BEAR_HIGH_VOL: 'bg-red-100',
    UNKNOWN: 'bg-gray-50',
  };
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="by-regime-table">
      <h3 className="font-bold text-gray-900 mb-3" title="Качество модели в разных рыночных режимах">По режимам рынка</h3>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 px-3 font-medium text-gray-600">Режим</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600">Выборка</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600">Точность</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600">Ср. ошибка</th>
              <th className="text-center py-2 px-3 font-medium text-gray-600">P90</th>
            </tr>
          </thead>
          <tbody>
            {byRegime.map((r, i) => (
              <tr key={i} className={`border-b border-gray-100 ${regimeColors[r.regime] || ''}`}>
                <td className="py-2 px-3 font-medium" title={r.regime}>{regimeLabels[r.regime] || r.regime}</td>
                <td className="py-2 px-3 text-center">{r.sampleCount}</td>
                <td className="py-2 px-3 text-center font-mono">
                  <span className={r.hitRate >= 55 ? 'text-green-600' : r.hitRate >= 50 ? 'text-yellow-600' : 'text-red-600'}>
                    {r.hitRate}%
                  </span>
                </td>
                <td className="py-2 px-3 text-center font-mono">{r.avgAbsError}%</td>
                <td className="py-2 px-3 text-center font-mono text-gray-600">{r.p90}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════

export function DriftTab({ asset = 'BTC' }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [windowDays, setWindowDays] = useState(90);
  const [actionStatus, setActionStatus] = useState(null);
  
  // P6 State
  const [p6Data, setP6Data] = useState({
    byHorizon: null,
    rolling: null,
    byRegime: null,
    dataMode: 'LIVE'
  });
  const [includeSeed, setIncludeSeed] = useState(true);
  
  // Asset-specific endpoint
  const assetLower = (asset || 'btc').toLowerCase();
  
  const fetchIntelligence = useCallback(async (window = windowDays) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/fractal/v2.1/admin/drift/intelligence?symbol=${asset}&window=${window}`);
      const json = await res.json();
      if (json.ok) {
        setData(json);
        setError(null);
      } else {
        setError(json.error || 'Failed to fetch drift intelligence');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [windowDays, asset]);
  
  // Fetch P6 data
  const fetchP6Data = useCallback(async () => {
    try {
      const seedParam = includeSeed ? 'true' : 'false';
      const [byHorizonRes, rollingRes, byRegimeRes] = await Promise.all([
        fetch(`${API_BASE}/api/admin/${assetLower}/drift/by-horizon?includeSeed=${seedParam}`),
        fetch(`${API_BASE}/api/admin/${assetLower}/drift/rolling?horizon=30d&window=30&includeSeed=${seedParam}`),
        fetch(`${API_BASE}/api/admin/${assetLower}/drift/by-regime?horizon=30d&includeSeed=${seedParam}`)
      ]);
      
      const [byHorizon, rolling, byRegime] = await Promise.all([
        byHorizonRes.json(),
        rollingRes.json(),
        byRegimeRes.json()
      ]);
      
      setP6Data({
        byHorizon: byHorizon.byHorizon || [],
        rolling: rolling.points || [],
        byRegime: byRegime.byRegime || [],
        dataMode: byHorizon.dataMode || 'LIVE'
      });
    } catch (err) {
      console.error('[P6] Error fetching P6 data:', err);
    }
  }, [includeSeed, assetLower]);
  
  useEffect(() => {
    fetchIntelligence();
    fetchP6Data();
  }, [fetchIntelligence, fetchP6Data]);
  
  const handleWindowChange = (w) => {
    setWindowDays(w);
    fetchIntelligence(w);
  };
  
  const handleAction = async (action) => {
    if (action === 'openGovernance') {
      setSearchParams({ tab: 'governance' });
    } else if (action === 'openOps') {
      setSearchParams({ tab: 'ops' });
    } else if (action === 'writeSnapshot') {
      setActionStatus('Writing snapshot...');
      try {
        const res = await fetch(`${API_BASE}/api/fractal/v2.1/admin/drift/intelligence/snapshot?symbol=BTC`, {
          method: 'POST',
        });
        const json = await res.json();
        if (json.ok) {
          setActionStatus(`Snapshot written: ${json.severity} @ ${json.date}`);
          setTimeout(() => setActionStatus(null), 3000);
        } else {
          setActionStatus(`Error: ${json.error}`);
        }
      } catch (err) {
        setActionStatus(`Error: ${err.message}`);
      }
    }
  };
  
  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="flex items-center gap-3 text-gray-500">
          <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
          <span>Loading drift intelligence...</span>
        </div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="bg-red-50 border border-red-300 rounded-xl p-4 text-red-700">
          <strong>Error:</strong> {error}
        </div>
      </div>
    );
  }
  
  const meta = {
    liveSamples: data?.live?.metrics?.samples || 0,
    v2020Samples: data?.baselines?.V2020?.metrics?.samples || 0,
    v2014Samples: data?.baselines?.V2014?.metrics?.samples || 0,
  };
  
  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6" data-testid="drift-intelligence-tab">
      {/* Action Status Toast */}
      {actionStatus && (
        <div className="fixed bottom-4 right-4 bg-slate-900 text-white px-4 py-3 rounded-lg shadow-lg z-50">
          {actionStatus}
        </div>
      )}
      
      {/* Header */}
      <DriftHeader 
        verdict={data?.verdict} 
        meta={meta}
        windowDays={windowDays}
        onWindowChange={handleWindowChange}
      />
      
      {/* Cohort Cards */}
      <div className="grid md:grid-cols-3 gap-4">
        <CohortCard cohort={data?.live} isPrimary />
        <CohortCard cohort={data?.baselines?.V2020} />
        <CohortCard cohort={data?.baselines?.V2014} />
      </div>
      
      {/* Delta Matrix */}
      <DeltaMatrix deltas={data?.deltas} />
      
      {/* ═══════════════════════════════════════════════════════════════ */}
      {/* P6 METRICS SECTION */}
      {/* ═══════════════════════════════════════════════════════════════ */}
      <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-slate-900" title="Детальные метрики качества модели">Детальные метрики</h3>
          <button
            onClick={() => { setIncludeSeed(!includeSeed); setTimeout(fetchP6Data, 100); }}
            className={`px-3 py-1 text-sm rounded-lg transition-colors ${
              includeSeed 
                ? 'bg-amber-500 text-white' 
                : 'bg-gray-200 text-gray-700'
            }`}
            data-testid="seed-toggle-btn"
          >
            SEED {includeSeed ? 'ON' : 'OFF'}
          </button>
        </div>
        
        <div className="space-y-4">
          {/* P6-A: By Horizon */}
          <ByHorizonTable byHorizon={p6Data.byHorizon} dataMode={p6Data.dataMode} />
          
          {/* P6-B & P6-C Grid */}
          <div className="grid md:grid-cols-2 gap-4">
            <RollingTrend points={p6Data.rolling} />
            <ByRegimeTable byRegime={p6Data.byRegime} />
          </div>
        </div>
      </div>
      
      {/* Two Column Layout */}
      <div className="grid md:grid-cols-2 gap-4">
        <SeverityLadder thresholds={data?.thresholds} />
        <ActionsPanel verdict={data?.verdict} onAction={handleAction} />
      </div>
      
      {/* Breakdown Section */}
      <BreakdownSection breakdowns={data?.breakdowns} />
      
      {/* Meta Footer */}
      <div className="text-xs text-gray-400 text-right">
        Computed at: {data?.meta?.computedAt || '—'} | Engine: {data?.meta?.engineVersion || 'v2.1.0'}
      </div>
    </div>
  );
}

export default DriftTab;
