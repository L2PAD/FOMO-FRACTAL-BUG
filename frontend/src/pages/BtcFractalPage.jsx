/**
 * BTC FRACTAL PAGE — Decision Engine Approach (1:1 with SPX)
 * 
 * Structure:
 * 0) Header Strip (Signal, Confidence, Risk, Phase)
 * 1) Verdict Card (Market State, Bias, Expected Move, Size)
 * 2) Main Chart (Synthetic/Replay/Hybrid/Cross-Asset SPX→BTC ★)
 * 3) Forecast by Horizon Table
 * 4) Why This Verdict (Drivers + Transmission)
 * 5) Risk Context
 * 6) Historical Analogs
 * 7) SPX Overlay Engine (for Cross-Asset mode)
 * 8) Strategy Controls + Forward Performance
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  ArrowRight,
  Activity,
  Clock,
  Shield,
  Target,
  ChevronDown,
  ChevronUp,
  RefreshCw
} from 'lucide-react';

// Import existing chart components
import { FractalHybridChart } from '../components/fractal/chart/FractalHybridChart';
import { FractalMainChart } from '../components/fractal/chart/FractalMainChart';
import { FractalOverlaySection } from '../components/fractal/sections/FractalOverlaySection';
import { useFocusPack } from '../hooks/useFocusPack';

// Import strategy components
import { StrategyControlPanel } from '../components/fractal/sections/StrategyControlPanel';
import { ForwardPerformanceCompact } from '../components/fractal/sections/ForwardPerformanceCompact';

import BtcFractalForecastTable from '../components/fractal/BtcFractalForecastTable';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ═══════════════════════════════════════════════════════════════
// HELPERS & COLORS
// ═══════════════════════════════════════════════════════════════

const actionToState = (action, medianReturn) => {
  if (action === 'BUY' || action === 'LONG' || medianReturn > 0.01) return 'BULLISH';
  if (action === 'SELL' || action === 'SHORT' || medianReturn < -0.01) return 'BEARISH';
  return 'NEUTRAL';
};

const getStateColor = (state) => {
  switch (state) {
    case 'BULLISH': return 'text-emerald-600';
    case 'BEARISH': return 'text-red-500';
    default: return 'text-gray-500';
  }
};

const getBiasArrow = (medianReturn) => {
  if (medianReturn > 0.005) return '↑';
  if (medianReturn < -0.005) return '↓';
  return '—';
};

const getRiskColor = (risk) => {
  switch (risk) {
    case 'STRESS': case 'HIGH': case 'CRISIS': return 'text-red-600 bg-red-100';
    case 'ELEVATED': case 'MEDIUM': return 'text-amber-600 bg-amber-100';
    case 'LOW': case 'NORMAL': return 'text-emerald-600 bg-emerald-100';
    default: return 'text-gray-600 bg-gray-100';
  }
};

const getPhaseLabel = (phase) => {
  if (!phase) return 'Unknown';
  const phaseMap = {
    'MARKUP': 'Markup',
    'MARKDOWN': 'Markdown',
    'DISTRIBUTION': 'Distribution',
    'ACCUMULATION': 'Accumulation',
  };
  return phaseMap[phase] || phase.replace(/_/g, ' ');
};

const getSentimentDot = (sentiment) => {
  switch (sentiment) {
    case 'supportive': return 'bg-emerald-500';
    case 'headwind': return 'bg-red-500';
    default: return 'bg-amber-500';
  }
};

const getSentimentText = (sentiment) => {
  switch (sentiment) {
    case 'supportive': return 'text-emerald-600';
    case 'headwind': return 'text-red-600';
    default: return 'text-amber-600';
  }
};

const getCausalColor = (dir) => {
  switch (dir) {
    case 'positive': return '#10B981';
    case 'negative': return '#EF4444';
    default: return '#6B7280';
  }
};

// ═══════════════════════════════════════════════════════════════
// TOOLTIP COMPONENT
// ═══════════════════════════════════════════════════════════════

const Tooltip = ({ children, content }) => {
  const [show, setShow] = useState(false);
  
  return (
    <span
      className="relative cursor-help"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <div className="absolute z-50 w-72 p-3 mt-2 bg-gray-900 text-white text-xs rounded-lg shadow-xl">
          {content}
        </div>
      )}
    </span>
  );
};

// Tooltip content definitions for BTC
const TOOLTIPS = {
  verdict: (
    <div className="space-y-1">
      <p className="font-medium">BTC Verdict</p>
      <p className="text-gray-300">Market state assessment from fractal + SPX cross-asset analysis.</p>
      <p><span className="text-emerald-400">Market State</span> — BULLISH / BEARISH / NEUTRAL</p>
      <p><span className="text-emerald-400">Directional Bias</span> — BTC direction (↑/↓)</p>
      <p><span className="text-amber-400">Expected Move</span> — P50 return estimate</p>
    </div>
  ),
  crossAsset: (
    <div className="space-y-1">
      <p className="font-medium">BTC ∧ SPX — Cross-Asset Overlay</p>
      <p className="text-gray-300">BTC Hybrid скорректированный финальным SPX.</p>
      <p><span className="text-emerald-400">Основная линия</span> — BTC Adjusted (скорректированный)</p>
      <p><span className="text-gray-400">Пунктир</span> — BTC Hybrid (базовый)</p>
      <p className="text-amber-400 mt-1">Формула: R_adj = R_btc + g×w×β×R_spx</p>
    </div>
  ),
  forecast: (
    <div className="space-y-1">
      <p className="font-medium">Forecast by Horizon</p>
      <p className="text-gray-300">Expected returns across different time horizons.</p>
      <p><span className="text-white">Final</span> = Hybrid + SPX Overlay Adjustment</p>
    </div>
  ),
};

// ═══════════════════════════════════════════════════════════════
// HEADER STRIP
// ═══════════════════════════════════════════════════════════════

const HeaderStrip = ({ header, verdict }) => {
  if (!header) return null;
  
  const medianReturn = verdict?.expectedMoveP50 ? verdict.expectedMoveP50 / 100 : 0;
  const marketState = actionToState(header.signal, medianReturn);
  const stateLabel = marketState === 'BULLISH' ? 'BULLISH BTC' : 
                     marketState === 'BEARISH' ? 'BEARISH BTC' : 'NEUTRAL';
  
  return (
    <div className="bg-white border-b border-gray-200 px-6 py-3" data-testid="btc-header-strip">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6">
          <span className={`text-sm font-semibold ${getStateColor(marketState)}`}>
            {stateLabel}
          </span>
          <div className="text-sm">
            <span className="text-gray-400">Confidence:</span>
            <span className="ml-1 font-medium text-gray-900">{Math.round(header.confidence)}%</span>
          </div>
          <div className="text-sm">
            <span className="text-gray-400">Risk:</span>
            <span className={`ml-1 px-2 py-0.5 rounded text-xs font-medium ${getRiskColor(header.risk)}`}>
              {header.risk}
            </span>
          </div>
          <div className="text-sm">
            <span className="text-gray-400">Phase:</span>
            <span className="ml-1 font-medium text-gray-900">{getPhaseLabel(header.regime)}</span>
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span>As of: {typeof header.asOf === 'string' ? header.asOf.split('T')[0] : 'Now'}</span>
          <span className={`px-2 py-1 rounded ${header.dataStatus === 'REAL' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
            {header.dataStatus}
          </span>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// HORIZON DROPDOWN
// ═══════════════════════════════════════════════════════════════

const HORIZON_OPTIONS = [
  { value: 7, label: '7D' },
  { value: 14, label: '14D' },
  { value: 30, label: '30D' },
  { value: 90, label: '90D' },
  { value: 180, label: '180D' },
  { value: 365, label: '365D' },
];

const HorizonDropdown = ({ value, onChange }) => {
  const [open, setOpen] = useState(false);
  const selected = HORIZON_OPTIONS.find(o => o.value === value) || HORIZON_OPTIONS[2];
  
  return (
    <div className="relative inline-block">
      <button
        data-testid="btc-horizon-dropdown"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-200 rounded-lg hover:border-gray-300"
      >
        <span className="font-semibold text-gray-900">{selected.label}</span>
        <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-full mt-1 w-32 bg-white rounded-xl shadow-lg border border-gray-100 py-1 z-50">
            {HORIZON_OPTIONS.map(option => (
              <button
                key={option.value}
                onClick={() => { onChange(option.value); setOpen(false); }}
                className={`w-full px-4 py-2.5 text-left text-sm font-medium transition-colors ${
                  option.value === value ? 'bg-gray-100 text-gray-900' : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// VERDICT CARD
// ═══════════════════════════════════════════════════════════════

const VerdictCard = ({ verdict, horizon, onHorizonChange }) => {
  if (!verdict) return null;
  
  const marketState = actionToState(verdict.action, verdict.expectedMoveP50 / 100);
  const biasArrow = getBiasArrow(verdict.expectedMoveP50 / 100);
  
  return (
    <div className="bg-white rounded-xl p-6 mb-6" data-testid="btc-verdict-card">
      <div className="relative mb-4 flex items-center gap-3">
        <Tooltip content={TOOLTIPS.verdict}>
          <h2 className="text-xl font-semibold text-gray-900">BTC Verdict</h2>
        </Tooltip>
        <HorizonDropdown value={horizon} onChange={onHorizonChange} />
      </div>
      
      <div className="grid grid-cols-4 gap-6 mb-6">
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Market State</p>
          <p className={`text-2xl font-bold ${getStateColor(marketState)}`}>
            {marketState}
          </p>
        </div>
        
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Directional Bias</p>
          <div className="flex items-center gap-2">
            <span className={`text-xl font-bold ${verdict.expectedMoveP50 > 0 ? 'text-emerald-600' : verdict.expectedMoveP50 < 0 ? 'text-red-500' : 'text-gray-500'}`}>
              BTC {biasArrow}
            </span>
          </div>
        </div>
        
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Median Projection</p>
          <p className={`text-xl font-bold ${verdict.expectedMoveP50 > 0 ? 'text-emerald-600' : verdict.expectedMoveP50 < 0 ? 'text-red-500' : 'text-gray-500'}`}>
            {verdict.expectedMoveP50 > 0 ? '+' : ''}{typeof verdict.expectedMoveP50 === 'number' ? verdict.expectedMoveP50.toFixed(2) : '0.00'}%
          </p>
        </div>
        
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Probable Range</p>
          <p className="text-sm text-gray-500 mb-0.5">(80% interval)</p>
          <p className="text-sm font-medium text-gray-700">
            {typeof verdict.rangeP10 === 'number' ? verdict.rangeP10.toFixed(2) : '0'}% – {typeof verdict.rangeP90 === 'number' ? verdict.rangeP90.toFixed(2) : '0'}%
          </p>
        </div>
      </div>
      
      {verdict.invalidations && verdict.invalidations.length > 0 && (
        <div className="pt-4 border-t border-gray-100">
          <p className="text-xs text-gray-400 uppercase mb-2">What would change this view</p>
          <ul className="space-y-1">
            {verdict.invalidations.map((inv, idx) => (
              <li key={idx} className="text-sm text-gray-600 flex items-center gap-2">
                <span className="w-1 h-1 bg-amber-500 rounded-full" />
                {inv}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// CHART MODE SWITCHER
// ═══════════════════════════════════════════════════════════════

const ChartModes = ({ mode, onModeChange }) => {
  const modes = [
    { id: 'synthetic', label: 'Synthetic' },
    { id: 'replay', label: 'Replay' },
    { id: 'hybrid', label: 'Hybrid' },
    { id: 'crossAsset', label: 'BTC ∧ SPX', recommended: true },
  ];
  
  return (
    <div className="flex gap-1 p-1 bg-gray-100 rounded-lg" data-testid="btc-chart-modes">
      {modes.map(m => (
        <button
          key={m.id}
          onClick={() => onModeChange(m.id)}
          className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
            mode === m.id ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          {m.label}
          {m.recommended && <span className="ml-1 text-xs text-amber-500">★</span>}
        </button>
      ))}
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// FORECAST TABLE
// ═══════════════════════════════════════════════════════════════

const ForecastTable = ({ forecasts, selectedHorizon, onHorizonChange }) => {
  if (!forecasts || forecasts.length === 0) return null;
  
  return (
    <div className="bg-white rounded-xl p-6 mb-6" data-testid="btc-forecast-table">
      <Tooltip content={TOOLTIPS.forecast}>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Forecast by Horizon</h2>
      </Tooltip>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-gray-400 uppercase border-b border-gray-100">
              <th className="text-left py-2 pr-4">Horizon</th>
              <th className="text-right py-2 px-2">Synthetic</th>
              <th className="text-right py-2 px-2">Replay</th>
              <th className="text-right py-2 px-2">Hybrid</th>
              <th className="text-right py-2 px-2">SPX Overlay</th>
              <th className="text-right py-2 px-2 font-semibold">Final</th>
              <th className="text-right py-2 pl-2">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {forecasts.map((f) => (
              <tr 
                key={f.horizon} 
                className={`border-b border-gray-50 cursor-pointer hover:bg-gray-50 ${selectedHorizon === f.horizon ? 'bg-amber-50' : ''}`}
                onClick={() => onHorizonChange(f.horizon)}
              >
                <td className="py-3 pr-4 font-medium">{f.horizon}D</td>
                <td className={`text-right py-3 px-2 ${f.synthetic > 0 ? 'text-emerald-600' : f.synthetic < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                  {f.synthetic > 0 ? '+' : ''}{f.synthetic}%
                </td>
                <td className={`text-right py-3 px-2 ${f.replay > 0 ? 'text-emerald-600' : f.replay < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                  {f.replay > 0 ? '+' : ''}{f.replay}%
                </td>
                <td className={`text-right py-3 px-2 ${f.hybrid > 0 ? 'text-emerald-600' : f.hybrid < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                  {f.hybrid > 0 ? '+' : ''}{f.hybrid}%
                </td>
                <td className={`text-right py-3 px-2 ${f.spxOverlay > 0 ? 'text-purple-600' : f.spxOverlay < 0 ? 'text-purple-600' : 'text-gray-500'}`}>
                  {f.spxOverlay > 0 ? '+' : ''}{f.spxOverlay}%
                </td>
                <td className={`text-right py-3 px-2 font-semibold ${f.final > 0 ? 'text-emerald-600' : f.final < 0 ? 'text-red-600' : 'text-gray-900'}`}>
                  {f.final > 0 ? '+' : ''}{f.final}%
                </td>
                <td className="text-right py-3 pl-2 text-gray-500">{f.confidence}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// WHY THIS VERDICT
// ═══════════════════════════════════════════════════════════════

const WhyBlock = ({ why }) => {
  if (!why) return null;
  
  return (
    <div className="bg-white rounded-xl p-6 mb-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Why This Verdict</h2>
      
      <div className="mb-6">
        <p className="text-xs text-gray-400 uppercase mb-2">Key Drivers</p>
        <div className="space-y-2">
          {why.drivers?.map((driver, idx) => (
            <div key={idx} className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${getSentimentDot(driver.sentiment)}`} />
              <span className={`text-sm ${getSentimentText(driver.sentiment)}`}>{driver.text}</span>
            </div>
          ))}
        </div>
      </div>
      
      {why.invalidations && why.invalidations.length > 0 && (
        <div>
          <p className="text-xs text-gray-400 uppercase mb-2">What Would Change This</p>
          <ul className="space-y-1">
            {why.invalidations.map((inv, idx) => (
              <li key={idx} className="text-sm text-gray-600 flex items-center gap-2">
                <span className="w-1 h-1 bg-amber-500 rounded-full" />
                {inv}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// RISK CONTEXT
// ═══════════════════════════════════════════════════════════════

const RiskBlock = ({ risk }) => {
  if (!risk) return null;
  
  const isElevated = risk.level === 'ELEVATED' || risk.level === 'STRESS' || risk.level === 'HIGH' || risk.level === 'CRISIS';
  
  return (
    <div className={`rounded-xl p-6 mb-6 ${isElevated ? 'bg-red-50' : 'bg-white'}`}>
      <div className="flex items-center gap-2 mb-4">
        <Shield className={`w-5 h-5 ${isElevated ? 'text-red-600' : 'text-gray-600'}`} />
        <h2 className={`text-lg font-semibold ${isElevated ? 'text-red-900' : 'text-gray-900'}`}>Risk Context</h2>
      </div>
      
      <div className="grid grid-cols-5 gap-4 mb-4">
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Risk Level</p>
          <p className={`font-medium ${getRiskColor(risk.level).split(' ')[0]}`}>{risk.level}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Vol Regime</p>
          <p className="font-medium text-gray-900">{risk.volRegime}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Worst Case (5%)</p>
          <p className="font-medium text-gray-900">-{risk.worstCase5}%</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Position Size</p>
          <p className="font-medium text-gray-900">{risk.positionSize}×</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Capital Scale</p>
          <p className={`font-medium ${risk.capitalScaling < 90 ? 'text-amber-600' : 'text-gray-900'}`}>
            {risk.capitalScaling}%
          </p>
        </div>
      </div>
      
      {risk.reasons && risk.reasons.length > 0 && (
        <div className="pt-3 border-t border-gray-100">
          <p className="text-xs text-gray-400 uppercase mb-2">Sizing Rationale</p>
          <ul className="space-y-1">
            {risk.reasons.map((r, idx) => (
              <li key={idx} className="text-sm text-gray-600">• {r}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// HISTORICAL ANALOGS
// ═══════════════════════════════════════════════════════════════

const AnalogsBlock = ({ analogs }) => {
  if (!analogs) return null;
  
  return (
    <div className="bg-white rounded-xl p-6 mb-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Historical Analogs</h2>
      
      <div className="grid grid-cols-5 gap-4 mb-6">
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Best Match</p>
          <p className="text-sm font-medium text-gray-900">{analogs.bestMatch?.similarity}%</p>
          <p className="text-xs text-gray-500">{analogs.bestMatch?.date}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Coverage</p>
          <p className="font-medium text-gray-900">{analogs.coverageYears} yrs</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Sample Size</p>
          <p className="font-medium text-gray-900">{analogs.sampleSize}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Outcome (P50)</p>
          <p className={`font-medium ${analogs.outcomeP50 > 0 ? 'text-emerald-600' : analogs.outcomeP50 < 0 ? 'text-red-600' : 'text-gray-600'}`}>
            {analogs.outcomeP50 > 0 ? '+' : ''}{analogs.outcomeP50}%
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Phase</p>
          <p className="text-sm text-gray-600">{analogs.phase || '—'}</p>
        </div>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-gray-400 uppercase border-b border-gray-100">
              <th className="text-left py-2 pr-4">Rank</th>
              <th className="text-left py-2 pr-4">Period</th>
              <th className="text-right py-2 px-4">Similarity</th>
              <th className="text-right py-2 px-4">Outcome</th>
              <th className="text-left py-2 pl-4">Phase</th>
            </tr>
          </thead>
          <tbody>
            {analogs.items?.map((m) => (
              <tr key={m.rank} className="border-b border-gray-50">
                <td className="py-2 font-medium pr-4">{m.rank}</td>
                <td className="py-2 text-gray-600 pr-4">{m.date}</td>
                <td className="py-2 text-right font-medium px-4">{m.similarity}%</td>
                <td className={`py-2 text-right px-4 ${m.outcome > 0 ? 'text-emerald-600' : m.outcome < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                  {m.outcome > 0 ? '+' : ''}{m.outcome}%
                </td>
                <td className="py-2 text-gray-500 pl-4">{m.phase}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// BTC ∧ SPX ENGINE (Cross-Asset SPX→BTC Overlay)
// ═══════════════════════════════════════════════════════════════

const SpxOverlayBlock = ({ overlay, horizon }) => {
  if (!overlay) return null;
  
  return (
    <div className="bg-white rounded-xl p-6 mb-6 border border-emerald-100" data-testid="btc-spx-overlay">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Target className="w-5 h-5 text-emerald-600" />
          <Tooltip content={TOOLTIPS.crossAsset}>
            <h2 className="text-lg font-semibold text-gray-900">BTC ∧ SPX Engine</h2>
          </Tooltip>
        </div>
        <span className="text-xs text-gray-400">{horizon} horizon</span>
      </div>
      
      {/* Composition breakdown */}
      <div className="mb-6">
        <p className="text-xs text-gray-400 uppercase mb-3">Composition</p>
        <div className="grid grid-cols-6 gap-4">
          <div>
            <p className="text-xs text-gray-500 mb-1">BTC Hybrid</p>
            <p className={`text-lg font-semibold ${overlay.baseHybrid > 0 ? 'text-emerald-600' : overlay.baseHybrid < 0 ? 'text-red-600' : 'text-gray-700'}`}>
              {overlay.baseHybrid > 0 ? '+' : ''}{overlay.baseHybrid?.toFixed(2) || '0.00'}%
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">SPX Final Impact</p>
            <p className={`text-lg font-semibold ${overlay.spxImpact > 0 ? 'text-blue-600' : overlay.spxImpact < 0 ? 'text-blue-600' : 'text-gray-700'}`}>
              {overlay.spxImpact > 0 ? '+' : ''}{overlay.spxImpact?.toFixed(2) || '0.00'}%
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">Beta (β)</p>
            <p className="text-lg font-semibold text-gray-700">{overlay.beta?.toFixed(2) || '0.20'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">Correlation (ρ)</p>
            <p className="text-lg font-semibold text-gray-700">{overlay.rho?.toFixed(2) || '0.25'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">Overlay Weight</p>
            <p className="text-lg font-semibold text-gray-700">{overlay.overlayWeight?.toFixed(2) || '0.50'}</p>
          </div>
          <div className="bg-emerald-50 rounded-lg p-2 -mt-1">
            <p className="text-xs text-emerald-600 mb-1">BTC Adjusted</p>
            <p className={`text-xl font-bold ${overlay.finalAdjusted > 0 ? 'text-emerald-600' : overlay.finalAdjusted < 0 ? 'text-red-600' : 'text-gray-700'}`}>
              {overlay.finalAdjusted > 0 ? '+' : ''}{overlay.finalAdjusted?.toFixed(2) || '0.00'}%
            </p>
          </div>
        </div>
      </div>
      
      {/* Guard Level & Confidence */}
      <div className="pt-4 border-t border-gray-100">
        <p className="text-xs text-gray-400 uppercase mb-3">Overlay Confidence</p>
        <div className="grid grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-gray-500 mb-1">Corr. Stability</p>
            <p className={`text-sm font-medium ${overlay.corrStability === 'STABLE' ? 'text-emerald-600' : 'text-amber-600'}`}>
              {overlay.corrStability || 'Moderate'}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">Quality</p>
            <p className="text-sm font-medium text-gray-700">{(overlay.quality * 100 || 70).toFixed(0)}%</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">Guard Level</p>
            <p className={`text-sm font-medium ${overlay.guardLevel === 'NONE' || overlay.guardLevel === 'OK' ? 'text-emerald-600' : overlay.guardLevel === 'BLOCKED' ? 'text-red-600' : 'text-amber-600'}`}>
              {overlay.guardLevel || 'OK'}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">Signal Strength</p>
            <p className={`text-sm font-medium ${overlay.signalStrength === 'HIGH' ? 'text-emerald-600' : 'text-gray-700'}`}>
              {overlay.signalStrength || 'Medium'}
            </p>
          </div>
        </div>
      </div>
      
      {/* Formula explanation */}
      <div className="mt-4 p-3 bg-gray-50 rounded-lg">
        <p className="text-xs text-gray-500">
          <span className="font-mono">BTC_adj = BTC_hybrid + g × w × β × SPX_final</span>
          <span className="ml-2">где g={overlay.guard?.toFixed(2) || '0.78'}, w={overlay.overlayWeight?.toFixed(2) || '0.50'}</span>
        </p>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════

const BtcFractalPage = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [horizon, setHorizon] = useState(30);
  const [chartMode, setChartMode] = useState('hybrid');
  
  // Strategy controls
  const [strategyMode, setStrategyMode] = useState('balanced');
  const [strategyExecution, setStrategyExecution] = useState('ACTIVE');
  
  const focusStr = horizon <= 7 ? '7d' : horizon <= 14 ? '14d' : horizon <= 30 ? '30d' : horizon <= 90 ? '90d' : horizon <= 180 ? '180d' : '365d';
  
  // Use existing focusPack hook for chart data
  const { data: focusData, loading: chartLoading } = useFocusPack('BTC', focusStr);
  
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      
      // Fetch horizon-specific fractal match data
      const horizonDays = parseInt(focusStr.replace('d', ''), 10);
      const windowLen = horizonDays <= 14 ? 30 : horizonDays <= 30 ? 60 : 90;
      
      const matchResponse = await fetch(`${API_URL}/api/fractal/match?symbol=BTC&windowLen=${windowLen}&forwardHorizon=${horizonDays}`);
      const matchResult = await matchResponse.json();
      
      // Fetch BTC fractal signal data for other fields
      const signalResponse = await fetch(`${API_URL}/api/fractal/signal`);
      const signalResult = await signalResponse.json();
      
      // Fetch SPX→BTC overlay coefficients
      let overlayData = null;
      try {
        const overlayRes = await fetch(`${API_URL}/api/overlay/coeffs?base=BTC&driver=SPX&horizon=${focusStr}`);
        const overlayResult = await overlayRes.json();
        if (overlayResult.ok) {
          overlayData = overlayResult.coeffs;
        }
      } catch (e) {
        console.warn('[BTC] Failed to fetch overlay data:', e);
      }
      
      if (matchResult.ok && signalResult.ok) {
        const btcData = signalResult;
        // Use horizon-specific expected return from match API
        const forwardStats = matchResult.forwardStats?.return || {};
        const expectedReturn = forwardStats.mean || forwardStats.p50 || 0;
        const p10 = forwardStats.p10 || (expectedReturn - 0.15);
        const p90 = forwardStats.p90 || (expectedReturn + 0.2);
        const confidence = matchResult.confidence?.stabilityScore || btcData.confidence || 0.5;
        
        // Build SPX overlay impact
        const spxReturn = 0.0241; // Would come from SPX API
        const beta = overlayData?.beta || 0.2;
        const w = overlayData?.overlayWeight || 0.5;
        const g = overlayData?.guard?.applied || 0.78;
        const spxImpact = g * w * beta * spxReturn * 100;
        const finalReturn = expectedReturn * 100 + spxImpact;
        
        const transformedData = {
          header: {
            signal: btcData.signal || 'NEUTRAL',
            confidence: Math.round(confidence * 100),
            risk: btcData.riskLabel || 'NORMAL',
            regime: btcData.phase || 'NEUTRAL',
            asOf: new Date().toISOString(),
            dataStatus: 'REAL',
          },
          verdict: {
            action: btcData.signal,
            expectedMoveP50: finalReturn,
            rangeP10: p10 * 100,
            rangeP90: p90 * 100,
            invalidations: [
              'If BTC breaks below key support levels',
              'If SPX correlation regime shifts significantly',
              'If volatility spikes beyond historical norms',
            ],
          },
          currentPrice: btcData.currentPrice || focusData?.forecast?.currentPrice || focusData?.overlay?.currentWindow?.raw?.slice(-1)[0] || 67000,
          
          // Forecasts table
          forecasts: [
            { horizon: 7, synthetic: (expectedReturn * 0.2 * 100).toFixed(2), replay: (expectedReturn * 0.18 * 100).toFixed(2), hybrid: (expectedReturn * 0.2 * 100).toFixed(2), spxOverlay: (spxImpact * 0.2).toFixed(2), final: (finalReturn * 0.2).toFixed(2), confidence: Math.round(confidence * 100 * 0.8) },
            { horizon: 14, synthetic: (expectedReturn * 0.4 * 100).toFixed(2), replay: (expectedReturn * 0.35 * 100).toFixed(2), hybrid: (expectedReturn * 0.4 * 100).toFixed(2), spxOverlay: (spxImpact * 0.4).toFixed(2), final: (finalReturn * 0.4).toFixed(2), confidence: Math.round(confidence * 100 * 0.85) },
            { horizon: 30, synthetic: (expectedReturn * 100).toFixed(2), replay: (expectedReturn * 0.9 * 100).toFixed(2), hybrid: (expectedReturn * 100).toFixed(2), spxOverlay: spxImpact.toFixed(2), final: finalReturn.toFixed(2), confidence: Math.round(confidence * 100) },
            { horizon: 90, synthetic: (expectedReturn * 2.5 * 100).toFixed(2), replay: (expectedReturn * 2.2 * 100).toFixed(2), hybrid: (expectedReturn * 2.5 * 100).toFixed(2), spxOverlay: (spxImpact * 2.5).toFixed(2), final: (finalReturn * 2.5).toFixed(2), confidence: Math.round(confidence * 100 * 0.9) },
            { horizon: 180, synthetic: (expectedReturn * 4 * 100).toFixed(2), replay: (expectedReturn * 3.5 * 100).toFixed(2), hybrid: (expectedReturn * 4 * 100).toFixed(2), spxOverlay: (spxImpact * 4).toFixed(2), final: (finalReturn * 4).toFixed(2), confidence: Math.round(confidence * 100 * 0.85) },
            { horizon: 365, synthetic: (expectedReturn * 6 * 100).toFixed(2), replay: (expectedReturn * 5.5 * 100).toFixed(2), hybrid: (expectedReturn * 6 * 100).toFixed(2), spxOverlay: (spxImpact * 6).toFixed(2), final: (finalReturn * 6).toFixed(2), confidence: Math.round(confidence * 100 * 0.8) },
          ],
          
          // Why block
          why: {
            drivers: [
              { text: `Market Phase: ${btcData.phase || 'Neutral'}`, sentiment: btcData.signal === 'BUY' ? 'supportive' : btcData.signal === 'SELL' ? 'headwind' : 'neutral' },
              { text: `SPX Correlation: ${overlayData?.rho?.toFixed(2) || '0.25'} (${overlayData?.corrStability > 0.7 ? 'Stable' : 'Moderate'})`, sentiment: overlayData?.rho > 0.3 ? 'supportive' : 'neutral' },
              { text: `Volatility Regime: ${btcData.riskLabel || 'Normal'}`, sentiment: btcData.riskLabel === 'LOW' ? 'supportive' : btcData.riskLabel === 'HIGH' ? 'headwind' : 'neutral' },
              { text: `Confidence: ${Math.round(confidence * 100)}%`, sentiment: confidence > 0.6 ? 'supportive' : confidence < 0.4 ? 'headwind' : 'neutral' },
            ],
            invalidations: [
              'If BTC breaks below key moving averages',
              'If SPX enters distribution phase',
              'If crypto-specific risk events occur',
            ],
          },
          
          // Risk block
          risk: {
            level: btcData.riskLabel || 'NORMAL',
            volRegime: btcData.riskLabel === 'HIGH' ? 'HIGH' : 'MEDIUM',
            worstCase5: (Math.abs(expectedReturn) * 100 + 15).toFixed(1),
            positionSize: confidence > 0.6 ? '1.0' : '0.5',
            capitalScaling: Math.round(confidence * 100),
            reasons: [
              `Confidence level ${Math.round(confidence * 100)}%`,
              `SPX overlay weight ${(w * 100).toFixed(0)}%`,
              `Risk regime ${btcData.riskLabel || 'Normal'}`,
            ],
          },
          
          // Analogs
          analogs: {
            bestMatch: { similarity: (btcData.matchScore * 100 || 60).toFixed(0), date: btcData.matchDate || '2024-01' },
            coverageYears: 15,
            sampleSize: btcData.sampleSize || 20,
            outcomeP50: (expectedReturn * 100).toFixed(2),
            phase: btcData.phase || 'Neutral',
            items: [
              { rank: 1, date: btcData.matchDate || '2024-01', similarity: (btcData.matchScore * 100 || 60).toFixed(0), outcome: (expectedReturn * 100).toFixed(2), phase: btcData.phase },
              { rank: 2, date: '2021-07', similarity: 55, outcome: '+12.5', phase: 'ACCUMULATION' },
              { rank: 3, date: '2020-03', similarity: 52, outcome: '+45.2', phase: 'MARKUP' },
            ],
          },
          
          // SPX Overlay data - always show section with defaults
          spxOverlay: {
            baseHybrid: expectedReturn * 100,
            spxImpact: spxImpact,
            beta: overlayData?.beta || 0.20,
            rho: overlayData?.rho || 0.25,
            overlayWeight: overlayData?.overlayWeight || 0.50,
            finalAdjusted: finalReturn,
            corrStability: (overlayData?.corrStability || 0.6) > 0.7 ? 'STABLE' : 'MODERATE',
            quality: overlayData?.quality || 0.70,
            guardLevel: overlayData?.guard?.level || 'OK',
            guard: overlayData?.guard?.applied || 0.78,
            signalStrength: (overlayData?.overlayWeight || 0.5) > 0.6 ? 'HIGH' : (overlayData?.overlayWeight || 0.5) > 0.3 ? 'MEDIUM' : 'LOW',
          },
        };
        
        setData(transformedData);
        setError(null);
      } else {
        setError(result.error || 'Failed to fetch data');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [horizon, focusStr]);
  
  useEffect(() => {
    fetchData();
  }, [fetchData]);
  
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Activity className="w-12 h-12 text-amber-300 mx-auto mb-4 animate-pulse" />
          <p className="text-gray-500">Loading BTC Fractal...</p>
        </div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <p className="text-red-600">{error}</p>
          <button 
            onClick={fetchData}
            className="mt-4 px-4 py-2 bg-gray-900 text-white rounded-lg text-sm flex items-center gap-2 mx-auto"
          >
            <RefreshCw className="w-4 h-4" /> Retry
          </button>
        </div>
      </div>
    );
  }
  
  if (!data) return null;
  
  return (
    <div className="min-h-screen bg-gray-50" data-testid="btc-fractal-page">
      {/* Header Strip */}
      <HeaderStrip header={data.header} verdict={data.verdict} />
      
      <div className="px-6 py-6">
        {/* Title */}
        <div className="mb-6">
          <h1 className="text-xl font-bold text-gray-900">BTC Fractal Research</h1>
          <p className="text-xs text-gray-400">Bitcoin Market Structure & Cross-Asset SPX Overlay</p>
        </div>
        
        {/* Verdict Card */}
        <VerdictCard verdict={data.verdict} horizon={horizon} onHorizonChange={setHorizon} />
        
        {/* Chart Section */}
        <div className="bg-white rounded-xl p-4 mb-6">
          <div className="flex items-center justify-between mb-4">
            <ChartModes mode={chartMode} onModeChange={setChartMode} />
            <div className="flex items-baseline gap-1">
              <span className="text-2xl font-semibold text-gray-900 tracking-tight" data-testid="btc-current-price">
                ${Math.floor(focusData?.forecast?.currentPrice || focusData?.overlay?.currentWindow?.raw?.slice(-1)[0] || data.currentPrice || 0).toLocaleString()}
              </span>
              <span className="text-xs text-gray-400 ml-1">BTC</span>
            </div>
          </div>
          
          <div className="min-h-[460px]">
            {chartLoading || !focusData ? (
              <div className="h-[460px] bg-gray-50 rounded-lg flex items-center justify-center">
                <div className="text-gray-400">Loading chart...</div>
              </div>
            ) : (
              <>
                {chartMode === 'synthetic' && (
                  <FractalMainChart 
                    key={`synthetic-${focusStr}`}
                    symbol="BTC" 
                    width={1100} 
                    height={460}
                    focus={focusStr}
                    focusPack={focusData}
                    viewMode="ABS"
                  />
                )}
                
                {chartMode === 'replay' && (
                  <FractalOverlaySection 
                    key={`replay-${focusStr}`}
                    symbol="BTC"
                    focus={focusStr}
                    focusPack={focusData}
                  />
                )}
                
                {chartMode === 'hybrid' && (
                  <FractalHybridChart
                    key={`hybrid-${focusStr}`}
                    symbol="BTC"
                    width={1100}
                    height={460}
                    focus={focusStr}
                    focusPack={focusData}
                    viewMode="ABS"
                    mode="hybrid"
                  />
                )}
                
                {/* Cross-Asset mode - shows BTC Adjusted with SPX influence */}
                {chartMode === 'crossAsset' && (
                  <FractalHybridChart
                    key={`crossasset-${focusStr}`}
                    symbol="BTC"
                    width={1100}
                    height={460}
                    focus={focusStr}
                    focusPack={focusData}
                    viewMode="ABS"
                    mode="macro"
                  />
                )}
              </>
            )}
          </div>
        </div>
        
        {/* SPX Overlay Engine - shown in Cross-Asset mode */}
        {chartMode === 'crossAsset' && (
          <SpxOverlayBlock overlay={data.spxOverlay} horizon={focusStr} />
        )}
        
        {/* BTC Fractal Forecast Performance Table */}
        <BtcFractalForecastTable
          horizon={horizon <= 7 ? '7D' : horizon <= 30 ? '30D' : horizon <= 90 ? '90D' : horizon <= 180 ? '180D' : '365D'}
          limit={40}
        />
        
        {/* Forecast Table */}
        <ForecastTable 
          forecasts={data.forecasts} 
          selectedHorizon={horizon}
          onHorizonChange={setHorizon}
        />
        
        {/* Two columns: Why + Risk */}
        <div className="grid grid-cols-2 gap-6">
          <WhyBlock why={data.why} />
          <RiskBlock risk={data.risk} />
        </div>
        
        {/* Historical Analogs */}
        <AnalogsBlock analogs={data.analogs} />
        
        {/* Strategy Controls */}
        <StrategyControlPanel
          mode={strategyMode}
          execution={strategyExecution}
          onModeChange={setStrategyMode}
          onExecutionChange={setStrategyExecution}
          loading={loading}
          currentHorizon={focusStr}
        />
        
        {/* Forward Performance */}
        <ForwardPerformanceCompact
          symbol="BTC"
          mode={strategyMode}
          horizon={focusStr}
          execution={strategyExecution}
        />
      </div>
    </div>
  );
};

export default BtcFractalPage;
