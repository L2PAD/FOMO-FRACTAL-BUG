import React, { useState } from 'react';
import { ExternalLink, ChevronDown, ChevronRight } from 'lucide-react';
import { IntelligenceBlock } from '../../../../../components/intelligence';
import type { TokenSignal, TokenScore } from '../hooks/useTokenIntelligence';

const shortAddr = (a: string) => a ? `${a.slice(0, 6)}...${a.slice(-4)}` : '';

const SIG_CONFIG: Record<string, { label: string; color: string; dot: string }> = {
  accumulation: { label: 'Accumulation', color: 'text-emerald-400', dot: 'bg-emerald-500' },
  distribution: { label: 'Distribution', color: 'text-red-400', dot: 'bg-red-500' },
  rotation: { label: 'Rotation', color: 'text-blue-400', dot: 'bg-blue-500' },
  momentum: { label: 'Momentum', color: 'text-purple-400', dot: 'bg-purple-500' },
  weakening: { label: 'Weakening', color: 'text-amber-400', dot: 'bg-amber-500' },
  cluster_activity: { label: 'Cluster', color: 'text-cyan-400', dot: 'bg-cyan-500' },
  exit: { label: 'Exit', color: 'text-amber-400', dot: 'bg-amber-500' },
};

function getConfidenceTier(conviction: number): { label: string; color: string } {
  if (conviction >= 70) return { label: 'STRONG', color: 'text-emerald-400' };
  if (conviction >= 55) return { label: 'MODERATE', color: 'text-amber-400' };
  return { label: 'WEAK', color: 'text-gray-500' };
}

export function TokenSignals({ signals, scores, loading }: { signals: TokenSignal[]; scores?: TokenScore[]; loading: boolean }) {
  const [expandedToken, setExpandedToken] = useState<string | null>(null);
  const timingMap = new Map<string, number>();
  const walletsMap = new Map<string, string[]>();
  if (scores) {
    for (const s of scores) {
      if (s.avg_timing > 0) timingMap.set(s.token, s.avg_timing);
      if (s.wallet_addresses && s.wallet_addresses.length > 0) walletsMap.set(s.token, s.wallet_addresses);
    }
  }

  if (loading && signals.length === 0) {
    return (
      <IntelligenceBlock dark testId="token-signals">
        <div className="py-8 text-center">
          <div className="animate-spin w-5 h-5 border-2 border-emerald-400 border-t-transparent rounded-full mx-auto" />
          <p className="text-gray-500 mt-2 text-xs">Scanning signals...</p>
        </div>
      </IntelligenceBlock>
    );
  }

  return (
    <IntelligenceBlock dark testId="token-signals">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em] mb-4">Smart Money Signals</h3>
      {signals.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-4">No signals detected</p>
      ) : (
        <div className="space-y-4">
          {signals.slice(0, 5).map((sig, i) => {
            const cfg = SIG_CONFIG[sig.signal_type] || SIG_CONFIG.accumulation;
            const barColor = sig.conviction >= 60 ? 'bg-emerald-400' : sig.conviction >= 50 ? 'bg-amber-400' : 'bg-gray-600';
            const leadTime = timingMap.get(sig.token);
            const tier = getConfidenceTier(sig.conviction);

            return (
              <div key={sig.signal_id} data-testid={`token-signal-${i}`}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
                    <span className="text-sm font-bold text-white">{sig.token}</span>
                    <span className={`text-[10px] font-bold uppercase ${cfg.color}`}>{cfg.label}</span>
                  </div>
                  <span className={`text-[10px] font-black ${tier.color}`} data-testid={`signal-tier-${i}`}>{tier.label}</span>
                </div>

                {/* Conviction bar */}
                <div className="flex items-center gap-2 mb-1.5">
                  <div className="flex-1 h-1 bg-gray-800 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${barColor} transition-all duration-700`} style={{ width: `${sig.conviction}%` }} />
                  </div>
                  <span className="text-xs font-bold tabular-nums text-gray-300 w-8 text-right">{sig.conviction}%</span>
                </div>

                {/* Meta row */}
                <div className="flex items-center gap-3 text-[10px] text-gray-500 mb-1">
                  <span>{sig.capital_fmt} capital</span>
                  <span>{sig.wallet_count} wallets</span>
                  {leadTime != null && (
                    <span className={leadTime >= 5 ? 'text-emerald-400 font-bold' : ''} data-testid={`signal-lead-${i}`}>
                      +{leadTime.toFixed(1)}h lead
                    </span>
                  )}
                </div>

                {sig.drivers.length > 0 && (
                  <div className="pl-3 space-y-0.5">
                    {sig.drivers.slice(0, 2).map((d, di) => (
                      <div key={di} className="text-[10px] text-gray-500 flex items-center gap-1.5">
                        <span className={`w-0.5 h-0.5 rounded-full ${cfg.dot}`} />{d}
                      </div>
                    ))}
                  </div>
                )}

                {/* Expandable wallet addresses */}
                {(() => {
                  const wallets = walletsMap.get(sig.token);
                  if (!wallets || wallets.length === 0) return null;
                  const isExpanded = expandedToken === sig.signal_id;
                  return (
                    <div className="mt-1.5">
                      <button onClick={() => setExpandedToken(isExpanded ? null : sig.signal_id)}
                        className="text-[10px] text-violet-400 hover:text-violet-300 font-semibold flex items-center gap-0.5 transition-colors"
                        data-testid={`signal-wallets-expand-${i}`}>
                        {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                        {sig.wallet_count} wallets
                      </button>
                      {isExpanded && (
                        <div className="mt-1 space-y-0.5 pl-2 border-l-2 border-violet-500/20">
                          {wallets.map((addr, wi) => (
                            <div key={addr} className="flex items-center gap-2 py-0.5 group/sw">
                              <span className="text-[9px] text-gray-600 tabular-nums w-3">{wi + 1}.</span>
                              <a href={`https://etherscan.io/address/${addr}`} target="_blank" rel="noopener noreferrer"
                                className="text-[10px] text-violet-400 font-mono hover:underline" data-testid={`signal-wallet-link-${i}-${wi}`}>
                                {shortAddr(addr)}
                              </a>
                              <a href={`https://etherscan.io/address/${addr}`} target="_blank" rel="noopener noreferrer"
                                className="opacity-0 group-hover/sw:opacity-100 transition-opacity">
                                <ExternalLink className="w-2.5 h-2.5 text-gray-500 hover:text-blue-400" />
                              </a>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })()}
              </div>
            );
          })}
        </div>
      )}
    </IntelligenceBlock>
  );
}
