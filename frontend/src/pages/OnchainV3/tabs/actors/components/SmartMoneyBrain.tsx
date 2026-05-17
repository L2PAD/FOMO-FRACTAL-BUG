import React, { useState } from 'react';
import { Zap, ChevronDown, ChevronRight, ExternalLink, Copy, Check } from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from '../../../../../components/ui/tooltip';
import { fmtUsd } from '../helpers';
import { addressUrl } from '../../../utils/explorer';
import type { NarrativeData, BrainSignal } from '../types/smartMoney';

const signalLabels: Record<string, { text: string; color: string; bg: string }> = {
  strong_bullish: { text: 'Strong Bullish', color: 'text-emerald-400', bg: '' },
  bullish: { text: 'Bullish', color: 'text-emerald-400', bg: '' },
  neutral: { text: 'Neutral', color: 'text-gray-400', bg: '' },
  bearish: { text: 'Bearish', color: 'text-red-400', bg: '' },
  strong_bearish: { text: 'Strong Bearish', color: 'text-red-400', bg: '' },
};

const BIAS_STYLE: Record<string, { color: string; label: string }> = {
  bullish: { color: 'text-emerald-400', label: 'Bullish' },
  bearish: { color: 'text-red-400', label: 'Bearish' },
  neutral: { color: 'text-gray-400', label: 'Neutral' },
};

export function SmartMoneyNarrativeBlock({ data, loading }: { data: NarrativeData | null; loading: boolean }) {
  if (loading && !data) {
    return (
      <div className="rounded-2xl bg-gray-900 intelligence-dark p-8 text-center" data-testid="narrative-block">
        <div className="animate-spin w-6 h-6 border-2 border-emerald-400 border-t-transparent rounded-full mx-auto" />
        <p className="text-gray-500 mt-3 text-sm">Computing market narrative...</p>
      </div>
    );
  }
  if (!data || data.narrative_type === 'no_data') return null;

  const bias = BIAS_STYLE[data.bias] || BIAS_STYLE.neutral;

  return (
    <div className="rounded-2xl bg-gray-900 intelligence-dark p-6" data-testid="narrative-block">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <Zap className="w-5 h-5 text-amber-400" />
          <h3 className="font-bold text-white">Smart Money Narrative</h3>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs font-bold uppercase ${bias.color}`} data-testid="narrative-bias">{bias.label}</span>
          <span className="text-xs text-gray-500">{data.confidence}% confidence</span>
        </div>
      </div>

      <p className="text-lg text-white font-medium leading-relaxed mb-4" data-testid="narrative-summary">{data.summary}</p>

      {data.drivers.length > 0 && (
        <div className="space-y-1.5" data-testid="narrative-drivers">
          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Drivers</p>
          {data.drivers.map((d, i) => (
            <div key={i} className="flex items-center gap-2">
              <div className="w-1 h-1 rounded-full bg-gray-500" />
              <span className="text-sm text-gray-400">{d}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function SmartMoneyBrainBlock({ signals, loading, chainId, onNavigateToWallet }: {
  signals: BrainSignal[];
  loading: boolean;
  chainId?: number;
  onNavigateToWallet?: (address: string, src: string, params?: Record<string, string>) => void;
}) {
  if (loading && signals.length === 0) {
    return (
      <div className="rounded-2xl bg-gray-900 intelligence-dark p-6 text-center" data-testid="brain-block">
        <div className="animate-spin w-6 h-6 border-2 border-emerald-400 border-t-transparent rounded-full mx-auto" />
        <p className="text-gray-500 mt-3 text-sm">Computing alpha signals...</p>
      </div>
    );
  }
  if (signals.length === 0) return null;

  return (
    <div className="rounded-2xl bg-gray-900 intelligence-dark overflow-hidden" data-testid="brain-block">
      <div className="px-6 py-4 flex items-center gap-3">
        <div className="w-9 h-9 flex items-center justify-center">
          <Zap className="w-5 h-5 text-emerald-400" />
        </div>
        <div>
          <h3 className="font-bold text-white">Smart Money Brain</h3>
          <p className="text-xs text-gray-500">Alpha Score per token based on all smart money signals</p>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3 px-6 pb-6">
        {signals.map((s) => (
          <BrainTokenCard key={s.token} signal={s} chainId={chainId} onNavigateToWallet={onNavigateToWallet} />
        ))}
      </div>
    </div>
  );
}

function BrainTokenCard({ signal: s, chainId, onNavigateToWallet }: {
  signal: BrainSignal;
  chainId?: number;
  onNavigateToWallet?: (address: string, src: string, params?: Record<string, string>) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const sl = signalLabels[s.signal] || signalLabels.neutral;
  const barColor = s.alpha_score >= 60 ? 'bg-emerald-400' : s.alpha_score >= 40 ? 'bg-amber-400' : 'bg-red-400';
  const scoreColor = s.alpha_score >= 60 ? 'text-emerald-400' : s.alpha_score >= 40 ? 'text-amber-400' : 'text-red-400';
  const hasWallets = s.wallet_addresses && s.wallet_addresses.length > 0;

  return (
    <div className="p-4 hover:bg-gray-800/30 transition-colors group" data-testid={`brain-token-${s.token}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-bold text-white">{s.token}</span>
        <span className={`text-[9px] font-bold ${sl.color}`}>{sl.text}</span>
      </div>
      <div className={`text-3xl font-bold ${scoreColor}`}>{s.alpha_score}</div>
      <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden mt-2">
        <div className={`h-full rounded-full ${barColor} transition-all duration-700`} style={{ width: `${s.alpha_score}%` }} />
      </div>
      <div className="mt-3 space-y-1">
        <div className="flex justify-between text-[10px]">
          <span className="text-gray-500">Net flow</span>
          <span className={s.net_flow_usd >= 0 ? 'text-emerald-400' : 'text-red-400'}>
            {s.net_flow_usd >= 0 ? '+' : ''}{fmtUsd(s.net_flow_usd)}
          </span>
        </div>
        <div className="flex justify-between text-[10px]">
          <span className="text-gray-500">Wallets</span>
          {hasWallets ? (
            <button onClick={() => setExpanded(!expanded)}
              className="text-violet-400 hover:text-violet-300 font-semibold flex items-center gap-0.5 transition-colors"
              data-testid={`brain-wallet-expand-${s.token}`}>
              {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              {s.wallet_count}
            </button>
          ) : (
            <span className="text-gray-300">{s.wallet_count}</span>
          )}
        </div>
        <div className="flex justify-between text-[10px]">
          <span className="text-gray-500">Timing</span>
          <span className={s.avg_timing >= 5 ? 'text-emerald-400' : 'text-gray-400'}>+{s.avg_timing}</span>
        </div>
      </div>

      {expanded && hasWallets && (
        <div className="mt-2 space-y-0.5 pl-2 border-l-2 border-violet-500/20">
          {s.wallet_addresses!.map((addr, i) => (
            <div key={addr} className="flex items-center gap-1.5 group/w py-0.5" data-testid={`brain-wallet-${s.token}-${i}`}>
              <span className="text-[9px] text-gray-600 tabular-nums w-3">{i + 1}.</span>
              <button onClick={() => onNavigateToWallet?.(addr, 'brain')}
                className="text-[10px] text-violet-400 hover:text-violet-300 font-mono transition-colors truncate">
                {addr.slice(0, 6)}...{addr.slice(-4)}
              </button>
              {chainId && (
                <a href={addressUrl(addr, chainId)} target="_blank" rel="noopener noreferrer"
                  className="opacity-0 group-hover/w:opacity-100 transition-opacity flex-shrink-0">
                  <ExternalLink className="w-2.5 h-2.5 text-gray-600 hover:text-blue-400" />
                </a>
              )}
            </div>
          ))}
        </div>
      )}

      {s.drivers.length > 0 && (
        <div className="mt-3 pt-2">
          <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-1">Drivers</div>
          {s.drivers.slice(0, 3).map((d, di) => (
            <div key={di} className="text-[10px] text-gray-400 flex items-center gap-1 mt-0.5">
              <span className={`w-1 h-1 rounded-full ${s.alpha_score >= 50 ? 'bg-emerald-500' : 'bg-red-500'}`} />
              {d}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
