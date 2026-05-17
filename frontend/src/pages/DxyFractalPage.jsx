/**
 * DXY FRACTAL PAGE — Decision Engine Approach
 * 
 * Structure:
 * 0) Header Strip (Signal, Confidence, Risk, Regime)
 * 1) Verdict Card (Action, Bias, Expected Move, Size)
 * 2) Main Chart (Synthetic/Replay/Hybrid/Macro)
 * 3) Forecast by Horizon Table
 * 4) Why This Verdict (Drivers + Transmission)
 * 5) Risk Context
 * 6) Historical Analogs
 * 7) Macro Impact (collapsible)
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

import DxyFractalForecastTable from '../components/fractal/DxyFractalForecastTable';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ═══════════════════════════════════════════════════════════════
// HELPERS & COLORS
// ═══════════════════════════════════════════════════════════════

// Convert action to market state
const actionToState = (action, bias) => {
  if (action === 'BUY' || bias === 'USD_UP') return 'BULLISH';
  if (action === 'SELL' || bias === 'USD_DOWN') return 'BEARISH';
  return 'HOLD';
};

const getStateColor = (state) => {
  switch (state) {
    case 'BULLISH': return 'text-emerald-600';
    case 'BEARISH': return 'text-red-500';
    default: return 'text-gray-500';
  }
};

const getStateBgColor = (state) => {
  switch (state) {
    case 'BULLISH': return 'bg-emerald-50';
    case 'BEARISH': return 'bg-red-50';
    default: return 'bg-gray-50';
  }
};

const getBiasIcon = (bias) => {
  switch (bias) {
    case 'USD_UP': return TrendingUp;
    case 'USD_DOWN': return TrendingDown;
    default: return Minus;
  }
};

const getBiasArrow = (bias) => {
  if (bias === 'USD_UP') return '↑';
  if (bias === 'USD_DOWN') return '↓';
  return '—';
};

const getRiskColor = (risk) => {
  switch (risk) {
    case 'STRESS': return 'text-red-600 bg-red-100';
    case 'ELEVATED': return 'text-amber-600 bg-amber-100';
    case 'LOW': return 'text-emerald-600 bg-emerald-100';
    default: return 'text-gray-600 bg-gray-100';
  }
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
// DARK TOOLTIP
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

// Tooltip content definitions
const TOOLTIPS = {
  verdict: (
    <div className="space-y-1">
      <p className="font-medium">DXY Verdict</p>
      <p className="text-gray-300">Market state assessment from fractal + macro analysis.</p>
      <p><span className="text-emerald-400">Market State</span> — BULLISH / BEARISH / HOLD</p>
      <p><span className="text-emerald-400">Directional Bias</span> — USD direction (↑/↓)</p>
      <p><span className="text-amber-400">Expected Move</span> — P50 return estimate</p>
    </div>
  ),
  synthetic: (
    <div className="space-y-1">
      <p className="font-medium">Synthetic (Baseline Fractal)</p>
      <p className="text-gray-300">Model-generated forecast using DXY historical patterns and current market structure.</p>
    </div>
  ),
  replay: (
    <div className="space-y-1">
      <p className="font-medium">Replay (Historical Analogs)</p>
      <p className="text-gray-300">Forward paths from best-matching historical periods weighted by similarity.</p>
    </div>
  ),
  hybrid: (
    <div className="space-y-1">
      <p className="font-medium">Hybrid (Combined)</p>
      <p className="text-gray-300">Blended signal from Synthetic + Replay with optimal weighting.</p>
    </div>
  ),
  macro: (
    <div className="space-y-1">
      <p className="font-medium">Macro (Final View)</p>
      <p className="text-gray-300">Hybrid adjusted by macro regime (Fed, inflation, credit conditions).</p>
      <p className="text-amber-400">This is the recommended view.</p>
    </div>
  ),
  forecast: (
    <div className="space-y-1">
      <p className="font-medium">Forecast by Horizon</p>
      <p className="text-gray-300">Expected returns across different time horizons.</p>
      <p><span className="text-white">Final</span> = Hybrid + Macro Adjustment</p>
    </div>
  ),
  risk: (
    <div className="space-y-1">
      <p className="font-medium">Risk Context</p>
      <p className="text-gray-300">Current risk environment and position sizing guidance.</p>
      <p><span className="text-emerald-400">100%</span> = Full size</p>
      <p><span className="text-amber-400">&lt;100%</span> = Reduced due to volatility</p>
    </div>
  ),
  analogs: (
    <div className="space-y-1">
      <p className="font-medium">Historical Analogs</p>
      <p className="text-gray-300">Best-matching historical periods and their forward outcomes.</p>
      <p>Outcome = median forward return on selected horizon.</p>
    </div>
  ),
  macroImpact: (
    <div className="space-y-1">
      <p className="font-medium">Macro Impact</p>
      <p className="text-gray-300">Adjustment to base forecast from macroeconomic factors:</p>
      <p><span className="text-emerald-400">Fed Funds</span> — Monetary policy stance</p>
      <p><span className="text-emerald-400">Inflation</span> — CPI/PPI trends</p>
      <p><span className="text-emerald-400">Credit</span> — Risk appetite signals</p>
      <p className="text-amber-400 mt-1">Positive = USD support, Negative = USD pressure</p>
    </div>
  ),
};

// ═══════════════════════════════════════════════════════════════
// HEADER STRIP
// ═══════════════════════════════════════════════════════════════

const HeaderStrip = ({ header, verdict }) => {
  if (!header) return null;
  
  // Convert to state-oriented terminology
  const marketState = actionToState(header.signal, verdict?.bias);
  const stateLabel = marketState === 'BULLISH' ? 'BULLISH USD' : 
                     marketState === 'BEARISH' ? 'BEARISH USD' : 'HOLD';
  
  return (
    <div className="bg-white border-b border-gray-200 px-6 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6">
          {/* Market State */}
          <span className={`text-sm font-semibold ${getStateColor(marketState)}`}>
            {stateLabel}
          </span>
          
          {/* Confidence */}
          <div className="text-sm">
            <span className="text-gray-400">Confidence:</span>
            <span className="ml-1 font-medium text-gray-900">{header.confidence}%</span>
          </div>
          
          {/* Risk */}
          <div className="text-sm">
            <span className="text-gray-400">Risk:</span>
            <span className={`ml-1 px-2 py-0.5 rounded text-xs font-medium ${getRiskColor(header.risk)}`}>
              {header.risk}
            </span>
          </div>
          
          {/* Regime */}
          <div className="text-sm">
            <span className="text-gray-400">Regime:</span>
            <span className="ml-1 font-medium text-gray-900">{header.regime?.replace('_', ' ')}</span>
          </div>
        </div>
        
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span>As of: {header.asOf}</span>
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
  const selected = HORIZON_OPTIONS.find(o => o.value === value) || HORIZON_OPTIONS[3];
  
  return (
    <div className="relative inline-block">
      <button
        data-testid="horizon-dropdown-trigger"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-200 rounded-lg hover:border-gray-300 transition-colors"
      >
        <span className="font-semibold text-emerald-600">{selected.label}</span>
        <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      
      {open && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          
          {/* Dropdown */}
          <div 
            data-testid="horizon-dropdown-menu"
            className="absolute left-0 top-full mt-1 w-32 bg-white rounded-xl shadow-lg border border-gray-100 py-1 z-50"
          >
            {HORIZON_OPTIONS.map(option => (
              <button
                key={option.value}
                data-testid={`horizon-option-${option.value}`}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                className={`w-full px-4 py-2.5 text-left text-sm font-medium transition-colors ${
                  option.value === value
                    ? 'bg-emerald-50 text-emerald-600'
                    : 'text-gray-600 hover:bg-gray-50'
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
  
  // Convert to state-oriented
  const marketState = actionToState(verdict.action, verdict.bias);
  const BiasIcon = getBiasIcon(verdict.bias);
  const biasArrow = getBiasArrow(verdict.bias);
  
  return (
    <div className="bg-white rounded-xl p-6 mb-6">
      <div className="relative mb-4 flex items-center gap-3">
        <Tooltip content={TOOLTIPS.verdict}>
          <h2 className="text-xl font-semibold text-gray-900">DXY Verdict</h2>
        </Tooltip>
        <HorizonDropdown value={horizon} onChange={onHorizonChange} />
      </div>
      
      <div className="grid grid-cols-5 gap-6 mb-6">
        {/* Market State */}
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Market State</p>
          <p className={`text-2xl font-bold ${getStateColor(marketState)}`}>
            {marketState}
          </p>
        </div>
        
        {/* Directional Bias */}
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Directional Bias</p>
          <div className="flex items-center gap-2">
            <span className={`text-xl font-bold ${verdict.bias === 'USD_UP' ? 'text-emerald-600' : verdict.bias === 'USD_DOWN' ? 'text-red-500' : 'text-gray-500'}`}>
              USD {biasArrow}
            </span>
          </div>
        </div>
        
        {/* Expected Move */}
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Expected (P50)</p>
          <p className={`text-xl font-bold ${verdict.expectedMoveP50 > 0 ? 'text-emerald-600' : verdict.expectedMoveP50 < 0 ? 'text-red-500' : 'text-gray-500'}`}>
            {verdict.expectedMoveP50 > 0 ? '+' : ''}{Number(verdict.expectedMoveP50).toFixed(2)}%
          </p>
        </div>
        
        {/* Range */}
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Range (P10–P90)</p>
          <p className="text-sm font-medium text-gray-700">
            {Number(verdict.rangeP10).toFixed(2)}% – {Number(verdict.rangeP90).toFixed(2)}%
          </p>
        </div>
        
        {/* Position Size */}
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Position Size</p>
          <p className="text-xl font-bold text-gray-900">{Number(verdict.positionMultiplier).toFixed(1)}×</p>
        </div>
      </div>
      
      {/* Invalidations */}
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
    { id: 'synthetic', label: 'Synthetic', tooltip: TOOLTIPS.synthetic },
    { id: 'replay', label: 'Replay', tooltip: TOOLTIPS.replay },
    { id: 'hybrid', label: 'Hybrid', tooltip: TOOLTIPS.hybrid },
    { id: 'macro', label: 'Macro', tooltip: TOOLTIPS.macro, recommended: true },
  ];
  
  return (
    <div className="flex gap-1 p-1 bg-gray-100 rounded-lg">
      {modes.map(m => (
        <Tooltip key={m.id} content={m.tooltip}>
          <button
            onClick={() => onModeChange(m.id)}
            className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
              mode === m.id
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {m.label}
            {m.recommended && <span className="ml-1 text-xs text-amber-500">★</span>}
          </button>
        </Tooltip>
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
    <div className="bg-white rounded-xl p-6 mb-6">
      <div className="relative mb-4">
        <Tooltip content={TOOLTIPS.forecast}>
          <h2 className="text-lg font-semibold text-gray-900">Forecast by Horizon</h2>
        </Tooltip>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-gray-400 uppercase border-b border-gray-100">
              <th className="text-left py-2 pr-4">Horizon</th>
              <th className="text-right py-2 px-2">Synthetic</th>
              <th className="text-right py-2 px-2">Replay</th>
              <th className="text-right py-2 px-2">Hybrid</th>
              <th className="text-right py-2 px-2">Macro Adj</th>
              <th className="text-right py-2 px-2 font-semibold">Final</th>
              <th className="text-right py-2 pl-2">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {forecasts.map((f) => (
              <tr 
                key={f.horizon} 
                className={`border-b border-gray-50 cursor-pointer hover:bg-gray-50 ${selectedHorizon === f.horizon ? 'bg-blue-50' : ''}`}
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
                <td className={`text-right py-3 px-2 ${f.macroAdj > 0 ? 'text-emerald-600' : f.macroAdj < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                  {f.macroAdj > 0 ? '+' : ''}{f.macroAdj}%
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
      
      {/* Drivers */}
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
      
      {/* Transmission */}
      <div className="mb-6">
        <p className="text-xs text-gray-400 uppercase mb-2">Macro Transmission</p>
        <div className="space-y-2">
          {why.transmission?.map((chain, idx) => (
            <div key={idx} className="flex items-center gap-1 flex-wrap">
              {chain.chain.map((link, linkIdx) => (
                <React.Fragment key={linkIdx}>
                  <span className="text-sm text-gray-700">{link.from}</span>
                  <ArrowRight className="w-3 h-3" style={{ color: getCausalColor(link.direction) }} />
                  {linkIdx === chain.chain.length - 1 && (
                    <span className="text-sm text-gray-700">{link.to}</span>
                  )}
                </React.Fragment>
              ))}
              <span className={`ml-2 text-sm font-medium ${
                chain.netEffect === 'positive' ? 'text-emerald-600' : 
                chain.netEffect === 'negative' ? 'text-red-600' : 'text-gray-600'
              }`}>
                → {chain.target}
              </span>
            </div>
          ))}
        </div>
      </div>
      
      {/* Invalidations */}
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
  
  const isElevated = risk.level === 'ELEVATED' || risk.level === 'STRESS';
  
  return (
    <div className={`rounded-xl p-6 mb-6 ${isElevated ? 'bg-red-50' : 'bg-white'}`}>
      <div className="flex items-center gap-2 mb-4">
        <Shield className={`w-5 h-5 ${isElevated ? 'text-red-600' : 'text-gray-600'}`} />
        <Tooltip content={TOOLTIPS.risk}>
          <h2 className={`text-lg font-semibold ${isElevated ? 'text-red-900' : 'text-gray-900'}`}>Risk Context</h2>
        </Tooltip>
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
          <p className="text-xs text-gray-400 uppercase mb-1">Exp. Drawdown</p>
          <p className="font-medium text-gray-900">-{risk.expectedDrawdown}%</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Position Size</p>
          <p className="font-medium text-gray-900">{risk.positionMultiplier}×</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Capital Scale</p>
          <p className={`font-medium ${risk.capitalScaling < 90 ? 'text-amber-600' : 'text-gray-900'}`}>
            {risk.capitalScaling}%
          </p>
        </div>
      </div>
      
      <p className="text-sm text-gray-600">{risk.scalingExplanation}</p>
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
      <div className="relative mb-4">
        <Tooltip content={TOOLTIPS.analogs}>
          <h2 className="text-lg font-semibold text-gray-900">Historical Analogs</h2>
        </Tooltip>
      </div>
      
      {/* Summary stats */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Best Match</p>
          <p className="text-sm font-medium text-gray-900">{analogs.bestMatch?.similarity}%</p>
          <p className="text-xs text-gray-500">{analogs.bestMatch?.dateRange}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Coverage</p>
          <p className="font-medium text-gray-900">{analogs.coverage} yrs</p>
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
          <p className="text-xs text-gray-400 uppercase mb-1">Range</p>
          <p className="text-sm text-gray-600">{analogs.outcomeP10}% … {analogs.outcomeP90}%</p>
        </div>
      </div>
      
      {/* Top matches table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-gray-400 uppercase border-b border-gray-100">
              <th className="text-left py-2">Rank</th>
              <th className="text-left py-2">Period</th>
              <th className="text-right py-2">Similarity</th>
              <th className="text-right py-2">Outcome</th>
              <th className="text-left py-2">Era</th>
            </tr>
          </thead>
          <tbody>
            {analogs.topMatches?.map((m) => (
              <tr key={m.rank} className="border-b border-gray-50">
                <td className="py-2 font-medium">#{m.rank}</td>
                <td className="py-2 text-gray-600">{m.dateRange}</td>
                <td className="py-2 text-right font-medium">{m.similarity}%</td>
                <td className={`py-2 text-right ${m.forwardReturn > 0 ? 'text-emerald-600' : m.forwardReturn < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                  {m.forwardReturn > 0 ? '+' : ''}{m.forwardReturn}%
                </td>
                <td className="py-2 text-gray-500">{m.decade}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// MACRO IMPACT (collapsible)
// ═══════════════════════════════════════════════════════════════

const MacroBlock = ({ macro }) => {
  if (!macro) return null;
  
  return (
    <div className="bg-white rounded-xl p-6">
      <div className="flex items-center justify-between w-full mb-4">
        <Tooltip content={TOOLTIPS.macroImpact}>
          <h2 className="text-lg font-semibold text-gray-900">Macro Impact</h2>
        </Tooltip>
        <span className={`font-medium ${macro.scoreSigned > 0 ? 'text-emerald-600' : macro.scoreSigned < 0 ? 'text-red-600' : 'text-gray-600'}`}>
          {macro.scoreSigned > 0 ? '+' : ''}{macro.scoreSigned}% adjustment
        </span>
      </div>
      
      <div className="pt-4 border-t border-gray-100">
        <div className="grid grid-cols-4 gap-4 mb-4">
          <div>
            <p className="text-xs text-gray-400 uppercase mb-1">Macro Score</p>
            <p className="font-medium text-gray-900">{macro.score}%</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 uppercase mb-1">Confidence</p>
            <p className="font-medium text-gray-900">{macro.confidence}%</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 uppercase mb-1">Regime</p>
            <p className="font-medium text-gray-900">{macro.regime}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 uppercase mb-1">Delta</p>
            <p className={`font-medium ${macro.deltaPct > 0 ? 'text-emerald-600' : macro.deltaPct < 0 ? 'text-red-600' : 'text-gray-600'}`}>
              {macro.deltaPct > 0 ? '+' : ''}{macro.deltaPct}%
            </p>
          </div>
        </div>
        
        {/* Components table */}
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-400 uppercase border-b border-gray-100">
                <th className="text-left py-2">Factor</th>
                <th className="text-right py-2">Pressure</th>
                <th className="text-right py-2">Weight</th>
                <th className="text-right py-2">Contribution</th>
              </tr>
            </thead>
            <tbody>
              {macro.components?.map((c) => (
                <tr key={c.key} className="border-b border-gray-50">
                  <td className="py-2 text-gray-700">{c.label}</td>
                  <td className={`py-2 text-right ${c.pressure > 0 ? 'text-emerald-600' : c.pressure < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                    {c.pressure > 0 ? '+' : ''}{c.pressure}%
                  </td>
                  <td className="py-2 text-right text-gray-500">{c.weight}%</td>
                  <td className={`py-2 text-right ${c.contribution > 0 ? 'text-emerald-600' : c.contribution < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                    {c.contribution > 0 ? '+' : ''}{c.contribution}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════

const DxyFractalPage = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [horizon, setHorizon] = useState(90);
  const [chartMode, setChartMode] = useState('macro');
  
  // Focus string for chart (e.g., '90d')
  const focusStr = horizon <= 7 ? '7d' : horizon <= 14 ? '14d' : horizon <= 30 ? '30d' : horizon <= 90 ? '90d' : horizon <= 180 ? '180d' : '1y';
  
  // Use existing focusPack hook for chart data
  const { data: focusData, loading: chartLoading, forecast, overlay } = useFocusPack('DXY', focusStr);
  
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/api/ui/fractal/dxy/overview?h=${horizon}`);
      const result = await response.json();
      
      if (result.ok) {
        setData(result);
        setError(null);
      } else {
        setError(result.error || 'Failed to fetch data');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [horizon]);
  
  useEffect(() => {
    fetchData();
  }, [fetchData]);
  
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Activity className="w-12 h-12 text-gray-300 mx-auto mb-4 animate-pulse" />
          <p className="text-gray-500">Loading DXY Fractal...</p>
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
    <div className="min-h-screen bg-gray-50">
      {/* Header Strip */}
      <HeaderStrip header={data.header} verdict={data.verdict} />
      
      <div className="px-6 py-6">
        {/* Title */}
        <div className="mb-6">
          <h1 className="text-xl font-bold text-gray-900">DXY Fractal Research</h1>
          <p className="text-xs text-gray-400">Dollar Index Analysis & Macro Overlay</p>
        </div>
        
        {/* Verdict Card */}
        <VerdictCard verdict={data.verdict} horizon={horizon} onHorizonChange={setHorizon} />
        
        {/* Chart Mode Switcher */}
        <div className="bg-white rounded-xl p-4 mb-6">
          <div className="flex items-center justify-between mb-4">
            <ChartModes mode={chartMode} onModeChange={setChartMode} />
            <div className="flex items-baseline gap-1">
              <span className="text-2xl font-semibold text-gray-900 tracking-tight">{Math.floor(data.currentPrice || 0)}</span>
              <span className="text-lg font-medium text-gray-400">.{((data.currentPrice || 0) % 1).toFixed(2).slice(2)}</span>
              <span className="text-xs text-gray-400 ml-1">DXY</span>
            </div>
          </div>
          {/* Real Chart - different components for different modes */}
          <div className="min-h-[460px]">
            {chartLoading || !focusData ? (
              <div className="h-[460px] bg-gray-50 rounded-lg flex items-center justify-center">
                <div className="text-gray-400">Loading chart...</div>
              </div>
            ) : (
              <>
                {/* Synthetic = FractalMainChart (price chart with forecast) */}
                {chartMode === 'synthetic' && (
                  <FractalMainChart 
                    symbol="DXY" 
                    width={1100} 
                    height={460}
                    focus={focusStr}
                    focusPack={focusData}
                    viewMode="ABS"
                  />
                )}
                
                {/* Replay = FractalOverlaySection (historical matches overlay) */}
                {chartMode === 'replay' && (
                  <FractalOverlaySection 
                    symbol="DXY"
                    focus={focusStr}
                    focusPack={focusData}
                  />
                )}
                
                {/* Hybrid = FractalHybridChart (combined synthetic + replay) */}
                {chartMode === 'hybrid' && (
                  <FractalHybridChart
                    symbol="DXY"
                    width={1100}
                    height={460}
                    focus={focusStr}
                    focusPack={focusData}
                    viewMode="ABS"
                    mode="hybrid"
                  />
                )}
                
                {/* Macro = FractalHybridChart with macro mode (hybrid + macro adjustment) */}
                {chartMode === 'macro' && (
                  <FractalHybridChart
                    symbol="DXY"
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
        
        {/* DXY Fractal Forecast Performance Table — above Forecast by Horizon */}
        <DxyFractalForecastTable
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
        
        {/* Macro Impact (collapsible) */}
        <MacroBlock macro={data.macro} />
      </div>
    </div>
  );
};

export default DxyFractalPage;
