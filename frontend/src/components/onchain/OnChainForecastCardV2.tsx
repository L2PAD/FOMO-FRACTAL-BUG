/**
 * OnChain Forecast Card V2
 * =========================
 * 
 * BLOCK O9.5: Forecast details card for OnChain Prediction UI
 * Shows governed output with multipliers and reasons
 * 
 * Features:
 * - Final score/confidence with raw comparison
 * - Applied governance multipliers
 * - State reason explanation
 * - Drivers list
 * - Flags summary
 */

import { useState, useEffect, useMemo } from 'react';
import { 
  TrendingUp as TrendingUpIcon, 
  TrendingDown as TrendingDownIcon, 
  Minus as MinusIcon,
  Shield as ShieldIcon,
  AlertTriangle as AlertTriangleIcon,
  Info as InfoIcon 
} from 'lucide-react';
import { OnchainFinalOutput, GuardrailState, GuardrailAction, OnchainFlag } from '../../lib/onchain/types';
import { formatGuardrailState, formatConfidence, biasLabel, formatPsi } from '../../lib/onchain/analytics';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

interface Props {
  symbol?: string;
  horizon?: string;
}

// Flag severity styling
const FLAG_STYLES: Record<string, string> = {
  CRITICAL: 'bg-red-100 text-red-700 border-red-200',
  WARN: 'bg-amber-100 text-amber-700 border-amber-200',
  INFO: 'bg-slate-100 text-slate-600 border-slate-200',
};

// State direction icons
function BiasIcon({ bias }: { bias: string }) {
  if (bias === 'Accumulating') return <TrendingUpIcon className="w-5 h-5 text-emerald-600" />;
  if (bias === 'Distributing') return <TrendingDownIcon className="w-5 h-5 text-red-600" />;
  return <MinusIcon className="w-5 h-5 text-gray-400" />;
}

export default function OnChainForecastCardV2({ symbol = 'ETH', horizon = '30D' }: Props) {
  const [data, setData] = useState<OnchainFinalOutput | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch data
  useEffect(() => {
    setLoading(true);
    setError(null);

    fetch(`${API_URL}/api/v10/onchain-v2/final/${symbol}`)
      .then(res => res.json())
      .then(json => {
        if (json.ok) {
          setData(json.output);
        } else {
          throw new Error(json.error || 'Failed to fetch');
        }
        setLoading(false);
      })
      .catch(err => {
        console.error('[OnChainCard] Error:', err);
        setError(err.message);
        setLoading(false);
      });
  }, [symbol]);

  // Derived values
  const bias = useMemo(() => biasLabel(data?.finalScore || 0.5), [data]);
  const guardrailConfig = useMemo(() => {
    return formatGuardrailState(data?.governance?.guardrailState || 'HEALTHY');
  }, [data]);
  
  // Calculate evaluation time (30d from now)
  const evaluateAt = useMemo(() => {
    const horizonMs: Record<string, number> = {
      '1D': 24 * 60 * 60 * 1000,
      '7D': 7 * 24 * 60 * 60 * 1000,
      '30D': 30 * 24 * 60 * 60 * 1000,
    };
    const ms = horizonMs[horizon] || horizonMs['30D'];
    return new Date(Date.now() + ms).toLocaleString();
  }, [horizon]);

  // Is confidence reduced?
  const isConfReduced = data && data.finalConfidence < (data.raw?.confidence || 0);
  const confReduction = data?.raw?.confidence 
    ? Math.round((1 - data.finalConfidence / data.raw.confidence) * 100)
    : 0;

  if (loading) {
    return (
      <div className="bg-gradient-to-r from-amber-50/50 to-orange-50/50 rounded-xl border border-amber-100 p-4 animate-pulse">
        <div className="h-4 bg-amber-100 rounded w-32 mb-3" />
        <div className="h-8 bg-amber-50 rounded w-48" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-slate-50 rounded-xl border border-slate-200 p-4">
        <div className="text-sm text-slate-500">OnChain data unavailable</div>
      </div>
    );
  }

  const isSafeMode = data.finalState === 'SAFE';
  const gov = data.governance;

  return (
    <div 
      className={`rounded-xl border p-4 ${
        isSafeMode 
          ? 'bg-gradient-to-r from-amber-50/80 to-orange-50/80 border-amber-200'
          : 'bg-gradient-to-r from-amber-50/50 to-orange-50/50 border-amber-100'
      }`}
      data-testid="onchain-forecast-card"
    >
      {/* Guardrail Header */}
      {gov?.guardrailAction !== 'NONE' && (
        <div className="flex items-center gap-2 mb-3 pb-3 border-b border-amber-200/50">
          <div 
            className={`px-2.5 py-1 rounded-full text-[10px] font-bold border ${guardrailConfig.color}`}
            title={gov.guardrailActionReasons?.join(', ') || 'Guardrails active'}
          >
            {gov.guardrailState}
          </div>
          
          {isConfReduced && (
            <div className="text-[11px] text-gray-500 flex items-center gap-1">
              <ShieldIcon className="w-3 h-3" />
              Confidence -{confReduction}%
            </div>
          )}
          
          <div className={`ml-auto px-3 py-1 rounded-lg text-xs font-bold shadow-sm ${
            isSafeMode ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-white' :
            gov.guardrailAction === 'DOWNWEIGHT' ? 'bg-gradient-to-r from-blue-500 to-cyan-500 text-white' :
            'bg-gradient-to-r from-gray-400 to-gray-500 text-white'
          }`}>
            {gov.guardrailAction === 'FORCE_SAFE' ? 'SAFE MODE' : gov.guardrailAction}
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        {/* Bias & State */}
        <div>
          <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide font-medium">
            {horizon} ONCHAIN SIGNAL
          </div>
          <div className="flex items-center gap-2">
            <BiasIcon bias={bias} />
            <span className={`text-xl font-bold ${
              bias === 'Accumulating' ? 'text-emerald-600' :
              bias === 'Distributing' ? 'text-red-600' : 'text-gray-700'
            }`}>
              {bias}
            </span>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {data.finalStateReason?.replace(/_/g, ' ')}
          </div>
        </div>

        {/* Score */}
        <div className="text-right">
          <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide font-medium">SCORE</div>
          <div className="flex items-center gap-1.5 justify-end">
            <span className="text-2xl font-bold text-gray-900">
              {Math.round(data.finalScore * 100)}
            </span>
            {data.raw && (
              <span className="text-sm text-gray-400 line-through">
                {Math.round(data.raw.score * 100)}
              </span>
            )}
          </div>
        </div>

        {/* Confidence */}
        <div className="text-right">
          <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide font-medium">CONFIDENCE</div>
          <div className="flex items-center gap-1.5 justify-end">
            <span className={`text-xl font-bold ${
              isSafeMode ? 'text-amber-600' : 'text-gray-900'
            }`}>
              {formatConfidence(data.finalConfidence)}
            </span>
            {isConfReduced && data.raw && (
              <span className="text-sm text-gray-400 line-through">
                {formatConfidence(data.raw.confidence)}
              </span>
            )}
          </div>
        </div>

        {/* Evaluate At */}
        <div className="text-right">
          <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide font-medium">EVALUATE AT</div>
          <div className="text-sm text-gray-600 font-medium">
            {evaluateAt}
          </div>
        </div>
      </div>

      {/* Drivers */}
      {data.drivers?.length > 0 && (
        <div className="mt-4 pt-3 border-t border-amber-200/30">
          <div className="text-[10px] text-gray-500 mb-2 uppercase tracking-wide font-medium">KEY DRIVERS</div>
          <div className="flex flex-wrap gap-1.5">
            {data.drivers.map((driver, i) => (
              <span 
                key={i}
                className="px-2 py-1 bg-white/60 border border-amber-100 rounded text-xs text-gray-700"
              >
                {driver.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Flags */}
      {data.flags?.length > 0 && (
        <div className="mt-3 pt-3 border-t border-amber-200/30">
          <div className="text-[10px] text-gray-500 mb-2 uppercase tracking-wide font-medium">FLAGS</div>
          <div className="flex flex-wrap gap-1.5">
            {data.flags.map((flag, i) => (
              <span 
                key={i}
                className={`px-2 py-1 border rounded text-[10px] font-medium ${FLAG_STYLES[flag.severity]}`}
                title={`Domain: ${flag.domain}`}
              >
                {flag.code}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Governance Multipliers */}
      {gov && (
        <div className="mt-3 pt-3 border-t border-amber-200/30">
          <div className="text-[10px] text-gray-500 mb-2 uppercase tracking-wide font-medium">APPLIED GOVERNANCE</div>
          <div className="flex flex-wrap gap-3 text-xs">
            <span className="text-gray-500">
              PSI: <span className={`font-medium ${
                gov.psi < 0.15 ? 'text-emerald-600' :
                gov.psi < 0.30 ? 'text-amber-600' : 'text-red-600'
              }`}>{formatPsi(gov.psi)}</span>
            </span>
            <span className="text-gray-500">
              Conf×: <span className="font-medium text-gray-700">{gov.confidenceModifier.toFixed(2)}</span>
            </span>
            <span className="text-gray-500">
              Samples: <span className="font-medium text-gray-700">{gov.sampleCount30d}</span>
            </span>
            {gov.emaApplied && (
              <span className="text-gray-400">EMA(α={gov.emaWindow})</span>
            )}
          </div>
        </div>
      )}

      {/* Source Attribution */}
      <div className="mt-3 pt-2 border-t border-amber-200/30 flex justify-end">
        <span className="text-[10px] text-gray-400">
          OnChain Module {gov?.policyVersion || 'v1.0.0'}
        </span>
      </div>
    </div>
  );
}
