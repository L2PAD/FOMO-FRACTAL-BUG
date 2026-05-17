/**
 * MACRO BRAIN — Decision Engine Page
 * 
 * Brain is not a dashboard. It's a decision engine.
 * It answers: Where are we? What to do? Why? How confident?
 */

import React, { useState, useEffect, useCallback } from 'react';
import { 
  TrendingUp, 
  TrendingDown,
  Minus,
  AlertTriangle,
  ArrowRight,
  Brain,
  Shield
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ═══════════════════════════════════════════════════════════════
// COLORS & HELPERS
// ═══════════════════════════════════════════════════════════════

const getSentimentColor = (sentiment) => {
  switch (sentiment) {
    case 'supportive': return 'text-emerald-600';
    case 'risk': return 'text-red-600';
    default: return 'text-amber-600';
  }
};

const getSentimentBg = (sentiment) => {
  switch (sentiment) {
    case 'supportive': return 'bg-emerald-50';
    case 'risk': return 'bg-red-50';
    default: return 'bg-amber-50';
  }
};

const getSentimentDot = (sentiment) => {
  switch (sentiment) {
    case 'supportive': return 'bg-emerald-500';
    case 'risk': return 'bg-red-500';
    default: return 'bg-amber-500';
  }
};

const getPostureStyles = (posture) => {
  switch (posture) {
    case 'OFFENSIVE': return { bg: 'bg-emerald-100', text: 'text-emerald-800' };
    case 'DEFENSIVE': return { bg: 'bg-red-100', text: 'text-red-800' };
    default: return { bg: 'bg-gray-100', text: 'text-gray-800' };
  }
};

const getBiasStyles = (bias) => {
  switch (bias) {
    case 'BULLISH': return { text: 'text-emerald-700', icon: TrendingUp };
    case 'BEARISH': return { text: 'text-red-700', icon: TrendingDown };
    default: return { text: 'text-gray-700', icon: Minus };
  }
};

const getPhaseColor = (phase) => {
  switch (phase) {
    case 'BULLISH': return 'text-emerald-600 bg-emerald-50';
    case 'BEARISH': return 'text-red-600 bg-red-50';
    default: return 'text-gray-600 bg-gray-50';
  }
};

const getStrengthWidth = (strength) => {
  switch (strength) {
    case 'strong': return 'w-full';
    case 'medium': return 'w-2/3';
    default: return 'w-1/3';
  }
};

const getCausalColor = (direction) => {
  switch (direction) {
    case 'positive': return '#10B981';
    case 'negative': return '#EF4444';
    default: return '#6B7280';
  }
};

// ═══════════════════════════════════════════════════════════════
// DARK TOOLTIP COMPONENT - Black design with colors
// ═══════════════════════════════════════════════════════════════

const SectionTooltip = ({ children, title, content }) => {
  const [show, setShow] = useState(false);
  
  return (
    <span 
      className="cursor-help border-b border-dotted border-gray-400"
      onMouseEnter={() => setShow(true)} 
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <div className="absolute z-50 w-80 p-4 mt-2 bg-gray-900 text-white text-sm rounded-lg shadow-xl">
          {title && <p className="font-semibold text-white mb-2">{title}</p>}
          <div className="text-gray-300 leading-relaxed">{content}</div>
        </div>
      )}
    </span>
  );
};

// Tooltip descriptions for each section
const TOOLTIPS = {
  verdict: {
    title: "Market Verdict",
    content: (
      <div className="space-y-2">
        <p>The final output of the macro analysis engine combining all signals.</p>
        <p><span className="text-emerald-400 font-medium">Regime</span> — Current market environment classification</p>
        <p><span className="text-emerald-400 font-medium">Bias</span> — Dominant directional tendency over 90 days</p>
        <p><span className="text-emerald-400 font-medium">Posture</span> — Recommended risk stance (Offensive/Defensive/Neutral)</p>
        <p><span className="text-amber-400 font-medium">Confidence</span> — Model certainty level (0-100%)</p>
      </div>
    )
  },
  reasons: {
    title: "Why This View",
    content: (
      <div className="space-y-2">
        <p>Key factors driving the current market assessment.</p>
        <p><span className="text-emerald-400">●</span> Green = Supportive for risk assets</p>
        <p><span className="text-amber-400">●</span> Orange = Neutral impact</p>
        <p><span className="text-red-400">●</span> Red = Risk factor / headwind</p>
      </div>
    )
  },
  horizons: {
    title: "Market Phase by Horizon",
    content: (
      <div className="space-y-2">
        <p>Expected market direction across different time horizons.</p>
        <p>Phase is derived from combined fractal pattern matching and macro regime analysis.</p>
        <p><span className="text-emerald-400 font-medium">Bullish</span> — Expected upward movement</p>
        <p><span className="text-red-400 font-medium">Bearish</span> — Expected downward movement</p>
        <p><span className="text-gray-400 font-medium">Neutral</span> — No clear directional bias</p>
        <p className="text-xs text-gray-500 mt-2">Strength: Weak → Medium → Strong</p>
      </div>
    )
  },
  risk: {
    title: "Risk Map",
    content: (
      <div className="space-y-2">
        <p>Current risk environment assessment.</p>
        <p><span className="text-white font-medium">Volatility</span> — Market volatility regime (Low/Normal/Elevated/Extreme)</p>
        <p><span className="text-white font-medium">Tail Risk</span> — Probability of extreme market moves</p>
        <p><span className="text-red-400 font-medium">Guard Status</span> — System protection level triggered</p>
        <p><span className="text-white font-medium">Capital Scale</span> — Exposure adjustment based on risk</p>
      </div>
    )
  },
  causal: {
    title: "Causal Flow",
    content: (
      <div className="space-y-2">
        <p>How macro factors transmit through markets.</p>
        <p><span className="text-emerald-400">→</span> Green arrow = Positive pressure</p>
        <p><span className="text-red-400">→</span> Red arrow = Negative pressure</p>
        <p><span className="text-gray-400">→</span> Gray arrow = Neutral</p>
        <p className="mt-2 text-xs">Example: Rising inflation → Higher rates → Stronger USD → Pressure on SPX</p>
      </div>
    )
  },
  macro: {
    title: "Macro Indicators",
    content: (
      <div className="space-y-2">
        <p>Real-time economic data from Federal Reserve (FRED).</p>
        <p>Hover on each indicator for detailed interpretation including normal ranges, risk zones, and market impacts.</p>
      </div>
    )
  },
  allocation: {
    title: "Allocation Pipeline",
    content: (
      <div className="space-y-2">
        <p>How the model transforms base allocations into final recommendations.</p>
        <p><span className="text-white font-medium">Base</span> — Starting allocation</p>
        <p><span className="text-white font-medium">After Brain</span> — After macro adjustments</p>
        <p><span className="text-white font-medium">Final</span> — After risk scaling applied</p>
      </div>
    )
  },
  scaling: {
    title: "Capital Scaling",
    content: (
      <div className="space-y-2">
        <p>Dynamic exposure adjustment based on market conditions.</p>
        <p><span className="text-emerald-400 font-medium">100%</span> = Full exposure allowed</p>
        <p><span className="text-amber-400 font-medium">70-99%</span> = Moderate reduction</p>
        <p><span className="text-red-400 font-medium">&lt;70%</span> = Significant risk reduction</p>
      </div>
    )
  }
};

// ═══════════════════════════════════════════════════════════════
// LAYER 1: FINAL VERDICT
// ═══════════════════════════════════════════════════════════════

const VerdictBlock = ({ verdict, action }) => {
  if (!verdict || !action) return null;
  
  const postureStyles = getPostureStyles(verdict.posture);
  const biasStyles = getBiasStyles(verdict.dominantBias);
  const BiasIcon = biasStyles.icon;
  
  return (
    <div className="mb-8">
      <div className="bg-white rounded-xl p-8">
        <div className="flex items-start justify-between mb-6">
          <div className="relative">
            <SectionTooltip {...TOOLTIPS.verdict}>
              <h2 className="text-2xl font-semibold text-gray-900">Market Verdict</h2>
            </SectionTooltip>
          </div>
          <div className={`px-4 py-2 rounded-full ${postureStyles.bg} ${postureStyles.text} font-medium text-sm`}>
            {verdict.posture}
          </div>
        </div>
        
        <div className="grid grid-cols-4 gap-6 mb-8">
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Regime</p>
            <p className="text-lg font-medium text-gray-900">{verdict.regime?.replace('_', ' ')}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Dominant Bias (90D)</p>
            <div className={`flex items-center gap-2 ${biasStyles.text}`}>
              <BiasIcon className="w-5 h-5" />
              <span className="text-lg font-medium">{verdict.dominantBias}</span>
            </div>
          </div>
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Posture</p>
            <p className="text-lg font-medium text-gray-900">{verdict.posture}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Confidence</p>
            <p className="text-lg font-medium text-gray-900">{verdict.confidence}%</p>
          </div>
        </div>
        
        <div className="bg-gray-50 rounded-lg p-6 mb-6">
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Primary Action</p>
          <p className="text-xl font-medium text-gray-900">{action.primary}</p>
        </div>
        
        <div className="grid grid-cols-3 gap-6">
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Size Multiplier</p>
            <p className="text-2xl font-semibold text-gray-900">{action.multiplier}x</p>
          </div>
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Cash Buffer</p>
            <p className="text-2xl font-semibold text-gray-900">{action.cashBufferRange}</p>
          </div>
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Leverage</p>
            <p className="text-2xl font-semibold text-gray-900">{action.leverageRecommended ? 'Yes' : 'No'}</p>
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// LAYER 2: WHY THIS VIEW
// ═══════════════════════════════════════════════════════════════

const ReasonsBlock = ({ reasons }) => {
  if (!reasons || reasons.length === 0) return null;
  
  return (
    <div className="bg-white rounded-xl p-6 mb-8">
      <div className="relative mb-4">
        <SectionTooltip {...TOOLTIPS.reasons}>
          <h2 className="text-lg font-semibold text-gray-900">Why This View</h2>
        </SectionTooltip>
      </div>
      <div className="space-y-3">
        {reasons.map((reason, idx) => (
          <div key={idx} className="flex items-center gap-3">
            <div className={`w-2 h-2 rounded-full ${getSentimentDot(reason.sentiment)}`} />
            <span className={`text-sm ${getSentimentColor(reason.sentiment)}`}>
              {reason.text}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// LAYER 3: HORIZON PHASE MAP
// ═══════════════════════════════════════════════════════════════

const HorizonBlock = ({ horizons }) => {
  if (!horizons || horizons.length === 0) return null;
  
  return (
    <div className="bg-white rounded-xl p-6 mb-8">
      <div className="relative mb-4">
        <SectionTooltip {...TOOLTIPS.horizons}>
          <h2 className="text-lg font-semibold text-gray-900">Market Phase by Horizon</h2>
        </SectionTooltip>
      </div>
      
      <div className="grid grid-cols-4 gap-4">
        {horizons.map((h) => (
          <div key={h.horizon} className="text-center">
            <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">{h.horizon}D</p>
            <div className={`py-3 px-4 rounded-lg ${getPhaseColor(h.phase)}`}>
              <p className="font-medium">{h.phase}</p>
              <p className="text-xs mt-1 opacity-70 capitalize">{h.strength}</p>
            </div>
            <div className="mt-2 h-1 bg-gray-100 rounded-full overflow-hidden">
              <div className={`h-full ${getStrengthWidth(h.strength)} ${h.phase === 'BULLISH' ? 'bg-emerald-500' : h.phase === 'BEARISH' ? 'bg-red-500' : 'bg-gray-400'}`} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// LAYER 4: RISK MAP
// ═══════════════════════════════════════════════════════════════

const RiskBlock = ({ risk }) => {
  if (!risk) return null;
  
  const isElevated = risk.guardStatus !== 'none' || risk.volatilityRegime === 'elevated' || risk.volatilityRegime === 'extreme';
  
  return (
    <div className={`rounded-xl p-6 mb-8 ${isElevated ? 'bg-red-50' : 'bg-white'}`}>
      <div className="flex items-center gap-2 mb-4 relative">
        <Shield className={`w-5 h-5 ${isElevated ? 'text-red-600' : 'text-gray-600'}`} />
        <SectionTooltip {...TOOLTIPS.risk}>
          <h2 className={`text-lg font-semibold ${isElevated ? 'text-red-900' : 'text-gray-900'}`}>Risk Map</h2>
        </SectionTooltip>
      </div>
      
      <div className="grid grid-cols-5 gap-4">
        <div>
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Volatility</p>
          <p className="font-medium text-gray-900 capitalize">{risk.volatilityRegime}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Tail Risk</p>
          <p className="font-medium text-gray-900 capitalize">{risk.tailRisk}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Guard Status</p>
          <p className={`font-medium capitalize ${risk.guardStatus !== 'none' ? 'text-red-600' : 'text-gray-900'}`}>
            {risk.guardStatus}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Override</p>
          <p className="font-medium text-gray-900">{risk.overrideIntensity}%</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Capital Scale</p>
          <p className="font-medium text-gray-900">{risk.capitalScaling}%</p>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// LAYER 5: CAUSAL FLOW - No borders on asset labels
// ═══════════════════════════════════════════════════════════════

const CausalBlock = ({ causal }) => {
  if (!causal || causal.length === 0) return null;
  
  return (
    <div className="bg-white rounded-xl p-6 mb-8">
      <div className="relative mb-4">
        <SectionTooltip {...TOOLTIPS.causal}>
          <h2 className="text-lg font-semibold text-gray-900">Causal Flow</h2>
        </SectionTooltip>
      </div>
      
      <div className="space-y-4">
        {causal.map((chain) => (
          <div key={chain.id} className="flex items-center gap-2 flex-wrap">
            {chain.links.map((link, idx) => (
              <React.Fragment key={idx}>
                <span className="text-sm font-medium text-gray-700">{link.from}</span>
                <ArrowRight 
                  className="w-4 h-4" 
                  style={{ color: getCausalColor(link.direction) }}
                />
                {idx === chain.links.length - 1 && (
                  <span className="text-sm font-medium text-gray-700">{link.to}</span>
                )}
              </React.Fragment>
            ))}
            <span className={`ml-2 text-sm font-semibold ${
              chain.netEffect === 'positive' ? 'text-emerald-600' :
              chain.netEffect === 'negative' ? 'text-red-600' :
              'text-gray-600'
            }`}>
              → {chain.targetAsset}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// LAYER 6: MACRO INDICATORS - Compact design
// ═══════════════════════════════════════════════════════════════

const MacroIndicatorCard = ({ indicator }) => {
  const [showTooltip, setShowTooltip] = useState(false);
  
  return (
    <div 
      className={`p-3 rounded-lg cursor-help relative ${getSentimentBg(indicator.status)}`}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <p className="text-xs text-gray-500 mb-1">{indicator.title}</p>
      <p className={`text-lg font-semibold ${getSentimentColor(indicator.status)}`}>
        {indicator.currentValue}
      </p>
      <p className="text-xs text-gray-500">{indicator.interpretation}</p>
      
      {showTooltip && (
        <div className="absolute z-50 w-64 p-3 bg-gray-900 text-white text-xs rounded-lg shadow-xl left-full ml-2 top-0">
          <p className="font-semibold text-white mb-2">{indicator.title}</p>
          <div className="space-y-1 text-gray-300">
            <p><span className="text-gray-500">Normal:</span> {indicator.normalRange}</p>
            <p><span className="text-red-400">Risk:</span> {indicator.riskRange}</p>
            <hr className="border-gray-700 my-2" />
            <p><span className="text-emerald-400">Bullish:</span> {indicator.bullishCondition}</p>
            <p><span className="text-red-400">Bearish:</span> {indicator.bearishCondition}</p>
          </div>
        </div>
      )}
    </div>
  );
};

const MacroBlock = ({ macroSummary }) => {
  if (!macroSummary || macroSummary.length === 0) return null;
  
  return (
    <div className="bg-white rounded-xl p-6 mb-8">
      <div className="relative mb-4">
        <SectionTooltip {...TOOLTIPS.macro}>
          <h2 className="text-lg font-semibold text-gray-900">Macro Indicators</h2>
        </SectionTooltip>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {macroSummary.map((indicator) => (
          <MacroIndicatorCard key={indicator.key} indicator={indicator} />
        ))}
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// LAYER 7: ALLOCATION PIPELINE
// ═══════════════════════════════════════════════════════════════

const AllocationBlock = ({ allocation }) => {
  if (!allocation) return null;
  
  const steps = [
    { label: 'Base', data: allocation.base },
    { label: 'After Brain', data: allocation.afterBrain },
    { label: 'Final', data: allocation.final },
  ];
  
  return (
    <div className="bg-white rounded-xl p-6 mb-8">
      <div className="relative mb-4">
        <SectionTooltip {...TOOLTIPS.allocation}>
          <h2 className="text-lg font-semibold text-gray-900">Allocation Pipeline</h2>
        </SectionTooltip>
      </div>
      
      <div className="flex items-center justify-between mb-6">
        {steps.map((step, idx) => (
          <React.Fragment key={step.label}>
            <div className="flex-1 text-center">
              <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">{step.label}</p>
              <div className="flex justify-center gap-4">
                <div>
                  <p className="text-xs text-gray-400">SPX</p>
                  <p className="font-medium text-gray-900">{step.data.spx}%</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">BTC</p>
                  <p className="font-medium text-gray-900">{step.data.btc}%</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">Cash</p>
                  <p className="font-medium text-gray-900">{step.data.cash}%</p>
                </div>
              </div>
            </div>
            {idx < steps.length - 1 && (
              <ArrowRight className="w-5 h-5 text-gray-300 mx-2" />
            )}
          </React.Fragment>
        ))}
      </div>
      
      <div className="grid grid-cols-4 gap-4 pt-4 border-t border-gray-100">
        <div>
          <p className="text-xs text-gray-400">Brain Impact</p>
          <p className="font-medium text-gray-900">{allocation.impact.brainImpact > 0 ? '+' : ''}{allocation.impact.brainImpact}%</p>
        </div>
        <div>
          <p className="text-xs text-gray-400">Optimizer Impact</p>
          <p className="font-medium text-gray-900">{allocation.impact.optimizerImpact > 0 ? '+' : ''}{allocation.impact.optimizerImpact}%</p>
        </div>
        <div>
          <p className="text-xs text-gray-400">Scaling Impact</p>
          <p className="font-medium text-gray-900">{allocation.impact.scalingImpact > 0 ? '+' : ''}{allocation.impact.scalingImpact}%</p>
        </div>
        <div>
          <p className="text-xs text-gray-400">Status</p>
          <p className="text-sm text-gray-600">{allocation.impact.explanation}</p>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// LAYER 8: CAPITAL SCALING
// ═══════════════════════════════════════════════════════════════

const CapitalScalingBlock = ({ capitalScaling }) => {
  if (!capitalScaling) return null;
  
  return (
    <div className="bg-white rounded-xl p-6 mb-8">
      <div className="flex items-center justify-between mb-4">
        <div className="relative">
          <SectionTooltip {...TOOLTIPS.scaling}>
            <h2 className="text-lg font-semibold text-gray-900">Capital Scaling</h2>
          </SectionTooltip>
        </div>
        <span className={`text-2xl font-bold ${
          capitalScaling.scaleFactor >= 90 ? 'text-emerald-600' :
          capitalScaling.scaleFactor >= 70 ? 'text-amber-600' :
          'text-red-600'
        }`}>{capitalScaling.scaleFactor}%</span>
      </div>
      
      <div className="grid grid-cols-3 gap-4 mb-4">
        {capitalScaling.drivers.map((driver) => (
          <div key={driver.name} className="p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-400">{driver.name}</p>
            <p className={`font-medium ${
              driver.effect === 'reduce' ? 'text-amber-600' : 'text-gray-900'
            }`}>{driver.value}%</p>
          </div>
        ))}
      </div>
      
      <p className="text-sm text-gray-600">{capitalScaling.explanation}</p>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// MAIN PAGE COMPONENT
// ═══════════════════════════════════════════════════════════════

const BrainOverviewPage = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/api/ui/brain/decision`);
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
  }, []);
  
  useEffect(() => {
    fetchData();
  }, [fetchData]);
  
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Brain className="w-12 h-12 text-gray-300 mx-auto mb-4 animate-pulse" />
          <p className="text-gray-500">Loading Macro Brain...</p>
          <p className="text-xs text-gray-400 mt-1">This may take up to 15 seconds</p>
        </div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <p className="text-red-600">Error loading data</p>
          <p className="text-sm text-gray-500 mt-1">{error}</p>
          <button 
            onClick={fetchData}
            className="mt-4 px-4 py-2 bg-gray-900 text-white rounded-lg text-sm"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }
  
  if (!data) return null;
  
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="px-6 py-6">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Macro Brain</h1>
          <p className="text-gray-500 mt-1">Institutional AI Macro Risk Dashboard</p>
        </div>
        
        {/* Layer 1: Verdict */}
        <VerdictBlock verdict={data.verdict} action={data.action} />
        
        {/* Layer 2: Reasons */}
        <ReasonsBlock reasons={data.reasons} />
        
        {/* Layer 3: Horizons */}
        <HorizonBlock horizons={data.horizons} />
        
        {/* Layer 4: Risk */}
        <RiskBlock risk={data.risk} />
        
        {/* Layer 5: Causal Flow */}
        <CausalBlock causal={data.causal} />
        
        {/* Layer 6: Macro Indicators */}
        <MacroBlock macroSummary={data.macroSummary} />
        
        {/* Layer 7: Allocation */}
        <AllocationBlock allocation={data.allocation} />
        
        {/* Layer 8: Capital Scaling */}
        <CapitalScalingBlock capitalScaling={data.capitalScaling} />
        
        {/* No Model Transparency or Advanced blocks - admin only */}
      </div>
    </div>
  );
};

export default BrainOverviewPage;
