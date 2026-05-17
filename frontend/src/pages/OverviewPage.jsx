/**
 * OVERVIEW PAGE — Market Verdict with TradingView-like Chart
 * 
 * LAYOUT:
 * 1. Top Bar — Asset + Horizon Switchers
 * 2. BIG CHART (65vh) — Hero element with candles + prediction
 * 3. Verdict Banner — Stance, Confidence, Summary
 * 4. Action Card + Reasons + Risks (3-column grid)
 * 5. Signal Stack — Key indicators
 * 6. Pipeline Summary — Signal transformation flow
 * 7. Forecast by Horizon — Table
 * 8. Meta Footer
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
  RefreshCw,
  CheckCircle,
  XCircle,
  Info
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Lazy load LivePredictionChart
import LivePredictionChart from '../components/charts/LivePredictionChart';

// ═══════════════════════════════════════════════════════════════
// HELPERS & COLORS
// ═══════════════════════════════════════════════════════════════

const getStanceColor = (stance) => {
  switch (stance) {
    case 'BULLISH': return 'text-emerald-600';
    case 'BEARISH': return 'text-red-500';
    default: return 'text-gray-500';
  }
};

const getStanceBgColor = (stance) => {
  switch (stance) {
    case 'BULLISH': return 'bg-emerald-50';
    case 'BEARISH': return 'bg-red-50';
    default: return 'bg-gray-50';
  }
};

const getStanceIcon = (stance) => {
  switch (stance) {
    case 'BULLISH': return <TrendingUp className="w-5 h-5" />;
    case 'BEARISH': return <TrendingDown className="w-5 h-5" />;
    default: return <Minus className="w-5 h-5" />;
  }
};

const getSeverityColor = (severity) => {
  switch (severity) {
    case 'HIGH': return 'text-red-600 bg-red-50';
    case 'MEDIUM': return 'text-amber-600 bg-amber-50';
    default: return 'text-gray-600 bg-gray-50';
  }
};

const getIndicatorStatusColor = (status) => {
  switch (status) {
    case 'GOOD': return 'bg-emerald-500';
    case 'BAD': return 'bg-red-500';
    default: return 'bg-gray-400';
  }
};

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
    case 'INCREASE_RISK': 
      return 'Market conditions support risk. Consider gradually increasing exposure to growth assets.';
    case 'REDUCE_RISK': 
      return 'Defense mode recommended. Reduce position sizes and increase cash allocation.';
    case 'HOLD_WAIT': 
      return 'Signal strength is weak. Wait for clearer confirmation before acting.';
    case 'HEDGE': 
      return 'Elevated tail risk detected. Consider protective positions or hedges.';
    default: 
      return 'Maintain current allocation. Monitor for changes in market conditions.';
  }
};

// ═══════════════════════════════════════════════════════════════
// TOOLTIP COMPONENT
// ═══════════════════════════════════════════════════════════════

const Tooltip = ({ children, content }) => {
  const [show, setShow] = useState(false);
  
  return (
    <div className="relative inline-block">
      <div
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
      >
        {children}
      </div>
      {show && content && (
        <div className="absolute z-50 w-64 p-3 text-sm bg-white border border-gray-200 rounded-lg shadow-lg -top-2 left-full ml-2">
          {content}
        </div>
      )}
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// COMPONENTS
// ═══════════════════════════════════════════════════════════════

// A) VERDICT BANNER — Market Verdict
const VerdictBanner = ({ verdict, asset, horizon }) => {
  if (!verdict) return null;
  
  const assetLabels = { dxy: 'Dollar Index', spx: 'S&P 500', btc: 'Bitcoin' };
  
  return (
    <div className={`p-6 rounded-lg ${getStanceBgColor(verdict.stance)}`} data-testid="verdict-banner">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <div className={`p-3 rounded-full ${verdict.stance === 'BULLISH' ? 'bg-emerald-100' : verdict.stance === 'BEARISH' ? 'bg-red-100' : 'bg-gray-100'}`}>
            {getStanceIcon(verdict.stance)}
          </div>
          <div>
            <div className="text-sm text-gray-500 uppercase tracking-wide">
              {assetLabels[asset]} • {horizon}d Horizon
            </div>
            <div className={`text-3xl font-bold ${getStanceColor(verdict.stance)}`}>
              {verdict.stance}
            </div>
          </div>
        </div>
        
        <div className="text-right">
          <Tooltip content="Model confidence based on signal clarity, data quality, and historical accuracy.">
            <div className="text-sm text-gray-500 cursor-help hover:text-gray-600 transition-colors">
              Confidence
            </div>
          </Tooltip>
          <div className="text-2xl font-semibold text-gray-800">
            {verdict.confidencePct}%
          </div>
        </div>
      </div>
      
      <p className="mt-4 text-gray-700">
        {verdict.summary}
      </p>
    </div>
  );
};

// B) ACTION CARD — What to do
const ActionCard = ({ verdict }) => {
  if (!verdict) return null;
  
  return (
    <div className="p-5 bg-white border border-gray-100 rounded-lg" data-testid="action-card">
      <div className="flex items-center gap-2 mb-3">
        <Target className="w-5 h-5 text-gray-400" />
        <h3 className="font-semibold text-gray-800">What To Do</h3>
      </div>
      
      <div className={`text-lg font-bold mb-2 ${getStanceColor(verdict.stance)}`}>
        {getActionHintText(verdict.actionHint)}
      </div>
      
      <p className="text-sm text-gray-600">
        {getActionHintDescription(verdict.actionHint)}
      </p>
    </div>
  );
};

// C) REASONS — Why this verdict
const ReasonsSection = ({ reasons }) => {
  if (!reasons || reasons.length === 0) return null;
  
  return (
    <div className="p-5 bg-white border border-gray-100 rounded-lg" data-testid="reasons-section">
      <div className="flex items-center gap-2 mb-4">
        <Activity className="w-5 h-5 text-gray-400" />
        <h3 className="font-semibold text-gray-800">Why This Verdict</h3>
      </div>
      
      <div className="space-y-3">
        {reasons.map((reason, idx) => (
          <div key={idx} className="flex items-start gap-3">
            <span className={`px-2 py-0.5 text-xs font-medium rounded ${getSeverityColor(reason.severity)}`}>
              {reason.severity}
            </span>
            <div className="flex-1">
              <div className="font-medium text-gray-800">{reason.title}</div>
              <div className="text-sm text-gray-600">{reason.text}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// D) RISKS — What can break the scenario
const RisksSection = ({ risks }) => {
  if (!risks || risks.length === 0) {
    return (
      <div className="p-5 bg-white border border-gray-100 rounded-lg" data-testid="risks-section">
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle className="w-5 h-5 text-amber-500" />
          <h3 className="font-semibold text-gray-800">Key Risks</h3>
        </div>
        <p className="text-sm text-gray-500">No significant risks identified</p>
      </div>
    );
  }
  
  return (
    <div className="p-5 bg-white border border-gray-100 rounded-lg" data-testid="risks-section">
      <div className="flex items-center gap-2 mb-4">
        <AlertTriangle className="w-5 h-5 text-amber-500" />
        <h3 className="font-semibold text-gray-800">Key Risks</h3>
      </div>
      
      <div className="space-y-3">
        {risks.map((risk, idx) => (
          <div key={idx} className="flex items-start gap-3">
            <span className={`px-2 py-0.5 text-xs font-medium rounded ${getSeverityColor(risk.severity)}`}>
              {risk.severity}
            </span>
            <div className="flex-1">
              <div className="font-medium text-gray-800">{risk.title}</div>
              <div className="text-sm text-gray-600">{risk.text}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// E) SIGNAL STACK — Key indicators
const SignalStack = ({ indicators }) => {
  const [expanded, setExpanded] = useState(false);
  
  if (!indicators || indicators.length === 0) return null;
  
  const visibleIndicators = expanded ? indicators : indicators.slice(0, 9);
  
  return (
    <div className="p-5 bg-white border border-gray-100 rounded-lg" data-testid="signal-stack">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between mb-4"
      >
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-gray-400" />
          <h3 className="font-semibold text-gray-800">Signal Stack</h3>
          <span className="text-xs text-gray-400">({indicators.length} indicators)</span>
        </div>
        {indicators.length > 9 && (
          expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />
        )}
      </button>
      
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {visibleIndicators.map((ind, idx) => (
          <Tooltip key={idx} content={ind.tooltip}>
            <div className="p-3 bg-gray-50 rounded-lg cursor-help hover:bg-gray-100 transition-colors">
              <div className="flex items-center gap-2 mb-1">
                <div className={`w-2 h-2 rounded-full ${getIndicatorStatusColor(ind.status)}`} />
                <span className="text-xs font-medium text-gray-500 uppercase">{ind.key}</span>
              </div>
              <div className="text-sm font-semibold text-gray-800">{ind.valueText}</div>
            </div>
          </Tooltip>
        ))}
      </div>
    </div>
  );
};

// F) PIPELINE SUMMARY — Signal flow (Redesigned)
const PipelineSummary = ({ pipeline, asset }) => {
  if (!pipeline) return null;
  
  const steps = [
    { 
      label: 'Data Inputs', 
      value: Object.keys(pipeline.macroScore || {}).length > 0 ? '12' : '0',
      unit: 'indicators',
      description: 'Macro economic time series feeding the model',
      color: 'from-blue-500 to-blue-600'
    },
    { 
      label: 'Macro Score', 
      value: pipeline.macroScore?.score?.toFixed(2) || '0.00',
      unit: 'z-score',
      description: 'Composite macro environment signal',
      color: 'from-purple-500 to-purple-600'
    },
    { 
      label: 'DXY Impact', 
      value: `${pipeline.dxyFinal?.projectionPct?.toFixed(1) || '0.0'}%`,
      unit: 'weight',
      description: 'Dollar strength influence on forecast',
      color: 'from-emerald-500 to-emerald-600'
    },
  ];
  
  if (asset !== 'dxy' && pipeline.spxOverlay) {
    steps.push({ 
      label: 'S&P 500', 
      value: `${pipeline.spxOverlay.projectionPct?.toFixed(1) || '0.0'}%`,
      unit: 'correlation',
      description: 'SPX cross-asset correlation factor',
      color: 'from-amber-500 to-amber-600'
    });
  }
  
  if (asset === 'btc' && pipeline.btcOverlay) {
    steps.push({ 
      label: 'BTC Adjusted', 
      value: `${pipeline.btcOverlay.projectionPct?.toFixed(1) || '0.0'}%`,
      unit: 'final',
      description: 'Final adjusted BTC forecast output',
      color: 'from-orange-500 to-orange-600'
    });
  }
  
  return (
    <div className="w-full" data-testid="pipeline-summary">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-gray-700 to-gray-800 flex items-center justify-center">
          <ArrowRight className="w-4 h-4 text-white" />
        </div>
        <div>
          <h3 className="font-semibold text-gray-800">Signal Pipeline</h3>
          <p className="text-xs text-gray-500">Data flow from inputs to final forecast</p>
        </div>
      </div>
      
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {steps.map((step, idx) => (
          <div 
            key={idx}
            className="group relative bg-white border border-gray-100 rounded-xl p-4 hover:border-gray-200 hover:shadow-sm transition-all duration-200"
          >
            {/* Progress indicator */}
            <div className="absolute top-0 left-0 right-0 h-1 rounded-t-xl overflow-hidden">
              <div className={`h-full w-full bg-gradient-to-r ${step.color} opacity-60`} />
            </div>
            
            {/* Step number */}
            <div className="flex items-start justify-between mb-2">
              <span className="text-[10px] font-medium text-gray-400 uppercase tracking-wider">
                Step {idx + 1}
              </span>
              {idx < steps.length - 1 && (
                <ArrowRight className="w-3 h-3 text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity hidden lg:block" />
              )}
            </div>
            
            {/* Content */}
            <div className="text-xs font-medium text-gray-500 mb-1">{step.label}</div>
            <div className="text-xl font-bold text-gray-900">{step.value}</div>
            <div className="text-[10px] text-gray-400 mt-1">{step.unit}</div>
            
            {/* Hover tooltip */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-xs rounded-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 whitespace-nowrap z-10 pointer-events-none">
              {step.description}
              <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1">
                <div className="border-4 border-transparent border-t-gray-900" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// G) FORECAST BY HORIZON — Table
const HorizonTable = ({ horizons }) => {
  if (!horizons || horizons.length === 0) return null;
  
  return (
    <div className="p-5 bg-white border border-gray-100 rounded-lg" data-testid="horizon-table">
      <div className="flex items-center gap-2 mb-4">
        <Clock className="w-5 h-5 text-gray-400" />
        <h3 className="font-semibold text-gray-800">Forecast by Horizon</h3>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-gray-100">
              <th className="pb-2 font-medium">Horizon</th>
              <th className="pb-2 font-medium">Stance</th>
              <th className="pb-2 font-medium">Median</th>
              <th className="pb-2 font-medium">Range</th>
              <th className="pb-2 font-medium">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {horizons.map((h, idx) => (
              <tr key={idx} className="border-b border-gray-50 last:border-0">
                <td className="py-2 font-medium text-gray-800">
                  {h.days === 'synthetic' ? 'Synthetic' : `${h.days}d`}
                </td>
                <td className={`py-2 font-semibold ${getStanceColor(h.stance)}`}>
                  {h.stance}
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
      
      <div className="mt-3 p-3 bg-gray-50 rounded text-xs text-gray-500">
        <strong>Synthetic</strong> = Aggregated signal across pattern structures. Not a separate market, but a weighted blend of historical analogs.
      </div>
    </div>
  );
};

// H) META FOOTER
const MetaFooter = ({ meta, latencyMs }) => {
  if (!meta) return null;
  
  return (
    <div className="flex items-center justify-between text-xs text-gray-400 pt-4 border-t border-gray-100" data-testid="meta-footer">
      <div className="flex items-center gap-4">
        <span>Version: {meta.systemVersion || 'v3.1'}</span>
        <span>Data: {meta.dataMode || 'mongo'}</span>
        <span className={meta.l5Grade === 'PRODUCTION' ? 'text-emerald-500' : 'text-amber-500'}>
          L5: {meta.l5Grade || 'PRODUCTION'}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <span>Latency: {latencyMs || 0}ms</span>
        <span>Hash: {meta.inputsHash?.slice(0, 8) || 'n/a'}</span>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// LOADING SKELETON
// ═══════════════════════════════════════════════════════════════

const LoadingSkeleton = () => (
  <div className="space-y-4 animate-pulse">
    {/* Verdict Skeleton */}
    <div className="p-6 bg-gray-100 rounded-lg">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-gray-200 rounded-full"></div>
          <div>
            <div className="w-32 h-3 bg-gray-200 rounded mb-2"></div>
            <div className="w-24 h-8 bg-gray-200 rounded"></div>
          </div>
        </div>
        <div className="text-right">
          <div className="w-20 h-3 bg-gray-200 rounded mb-2"></div>
          <div className="w-12 h-6 bg-gray-200 rounded"></div>
        </div>
      </div>
    </div>
    
    {/* 3-column grid skeleton */}
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {[1, 2, 3].map(i => (
        <div key={i} className="p-5 bg-white border border-gray-100 rounded-lg">
          <div className="w-24 h-4 bg-gray-200 rounded mb-3"></div>
          <div className="w-full h-4 bg-gray-100 rounded mb-2"></div>
          <div className="w-3/4 h-3 bg-gray-100 rounded"></div>
        </div>
      ))}
    </div>
    
    {/* Signal stack skeleton */}
    <div className="p-5 bg-white border border-gray-100 rounded-lg">
      <div className="w-32 h-4 bg-gray-200 rounded mb-4"></div>
      <div className="grid grid-cols-3 gap-3">
        {[1, 2, 3, 4, 5, 6].map(i => (
          <div key={i} className="p-3 bg-gray-50 rounded-lg">
            <div className="w-16 h-3 bg-gray-200 rounded mb-2"></div>
            <div className="w-12 h-4 bg-gray-200 rounded"></div>
          </div>
        ))}
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════

export default function OverviewPage() {
  // Read initial asset from URL params
  const getInitialAsset = () => {
    const params = new URLSearchParams(window.location.search);
    const urlAsset = params.get('asset')?.toLowerCase();
    return ['spx', 'btc', 'dxy'].includes(urlAsset) ? urlAsset : 'btc';
  };
  
  const getInitialHorizon = () => {
    const params = new URLSearchParams(window.location.search);
    const h = parseInt(params.get('horizon'));
    return [7, 14, 30, 90, 180, 365].includes(h) ? h : 90;
  };

  const [asset, setAsset] = useState(getInitialAsset);
  const [horizon, setHorizon] = useState(getInitialHorizon);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const res = await fetch(`${API_URL}/api/ui/overview?asset=${asset}&horizon=${horizon}`);
      const json = await res.json();
      
      if (!json.ok) {
        throw new Error(json.error || 'Failed to fetch overview');
      }
      
      setData(json);
      setLastUpdate(new Date());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [asset, horizon]);
  
  useEffect(() => {
    fetchData();
  }, [fetchData]);
  
  // Asset selector tabs (BTC first as default)
  const assetTabs = [
    { key: 'btc', label: 'Bitcoin', icon: '₿' },
    { key: 'spx', label: 'S&P 500', icon: '📊' },
    { key: 'dxy', label: 'Dollar', icon: '💵' },
  ];
  
  // Horizon selector
  const horizonOptions = [7, 14, 30, 90, 180, 365];
  
  // View mapping for prediction chart
  // V1 LOCKED: BTC must use crossAsset, SPX uses crossAsset, DXY uses hybrid
  const predictionView = asset === 'dxy' ? 'hybrid' : 'crossAsset';
  
  return (
    <div className="min-h-screen bg-gray-50" data-testid="overview-page">
      {/* ═══════════════════════════════════════════════════════════
          TOP BAR: Title + Asset Tabs + Horizon + Refresh
          ═══════════════════════════════════════════════════════════ */}
      <div className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-gray-100 h-[71px]">
        <div className="px-6 h-full flex items-center">
          <div className="flex items-center justify-between flex-wrap gap-4 w-full">
            {/* Left: Title */}
            <div>
              <h1 className="text-xl font-bold text-gray-900">Market Overview</h1>
              <p className="text-xs text-gray-400">One-screen verdict with actionable insights</p>
            </div>
            
            {/* Center: Asset Tabs */}
            <div className="flex bg-white border border-gray-200 rounded-lg p-1">
              {assetTabs.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setAsset(tab.key)}
                  data-testid={`asset-${tab.key}`}
                  className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                    asset === tab.key
                      ? 'bg-gray-900 text-white'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <span className="mr-1">{tab.icon}</span>
                  {tab.label}
                </button>
              ))}
            </div>
            
            {/* Right: Horizon + Refresh + Updated */}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500">Horizon:</span>
                <div className="flex bg-white border border-gray-200 rounded-lg p-1">
                  {horizonOptions.map((h) => (
                    <button
                      key={h}
                      onClick={() => setHorizon(h)}
                      data-testid={`horizon-${h}`}
                      className={`px-3 py-1.5 text-sm font-medium rounded transition-colors ${
                        horizon === h
                          ? 'bg-emerald-500 text-white'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      {h}d
                    </button>
                  ))}
                </div>
              </div>
              
              <button
                onClick={fetchData}
                disabled={loading}
                className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              </button>

              {lastUpdate && (
                <span className="text-xs text-gray-400 whitespace-nowrap">
                  Updated: {lastUpdate.toLocaleTimeString()}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
      
      {/* ═══════════════════════════════════════════════════════════
          MAIN CONTENT
          ═══════════════════════════════════════════════════════════ */}
      <div className="px-6 py-6">
        
        {/* Error State */}
        {error && (
          <div className="p-4 mb-6 bg-red-50 border border-red-200 rounded-lg text-red-700">
            <div className="flex items-center gap-2">
              <XCircle className="w-5 h-5" />
              <span className="font-medium">Error loading data</span>
            </div>
            <p className="mt-1 text-sm">{error}</p>
          </div>
        )}
        
        {/* ═══════════════════════════════════════════════════════
            1. BIG CHART — Hero Element (65vh)
            ═══════════════════════════════════════════════════════ */}
        <div className="mb-6">
          <LivePredictionChart
            asset={asset.toUpperCase()}
            horizonDays={horizon}
            view={predictionView}
          />
        </div>
        
        {/* Loading State */}
        {loading && !data && <LoadingSkeleton />}
        
        {/* Main Content Blocks */}
        {data && (
          <div className="space-y-4">
            {/* 2. Verdict Banner */}
            <VerdictBanner verdict={data.verdict} asset={asset} horizon={horizon} />
            
            {/* 3. Action Card + Reasons + Risks (3-column) */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <ActionCard verdict={data.verdict} />
              <ReasonsSection reasons={data.reasons} />
              <RisksSection risks={data.risks} />
            </div>
            
            {/* 4. Signal Stack */}
            <SignalStack indicators={data.indicators} />
            
            {/* 5. Pipeline Summary */}
            <PipelineSummary pipeline={data.pipeline} asset={asset} />
            
            {/* 6. Horizon Table */}
            <HorizonTable horizons={data.horizons} />
            
            {/* 7. Meta Footer */}
            <MetaFooter meta={data.meta} latencyMs={data.latencyMs} />
          </div>
        )}
      </div>
    </div>
  );
}
