import React, { useState } from 'react';
import {
  ArrowRight, RefreshCw, ExternalLink, Copy, Eye,
  Radar, Target, ArrowUpRight, ArrowDownRight, Shield, Users,
  ChevronDown, ChevronRight, Check,
} from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from '../../../../../components/ui/tooltip';
import { fmtUsd, shortAddr, copyToClipboard, timeSince } from '../helpers';
import { addressUrl, explorerName } from '../../../utils/explorer';
import type { RadarEvent, RadarSortKey } from '../types/smartMoney';

const sevConfig: Record<string, { color: string; bg: string }> = {
  CRITICAL: { color: 'text-red-700', bg: '' },
  HIGH: { color: 'text-amber-700', bg: '' },
  MEDIUM: { color: 'text-blue-700', bg: '' },
  LOW: { color: 'text-gray-500', bg: '' },
};
const classConfig: Record<string, string> = { wallet: 'Wallet', market: 'Market', cluster: 'Cluster' };

export function SmartMoneyRadarBlock({ events, loading, sortBy, onSortChange, onRefresh, onOpenWallet, onOpenEntity, chainId }: {
  events: RadarEvent[];
  loading: boolean;
  sortBy: RadarSortKey;
  onSortChange: (s: RadarSortKey) => void;
  onRefresh: () => void;
  onOpenWallet: (addr: string) => void;
  onOpenEntity: (id: string) => void;
  chainId: number;
}) {
  const eventConfig: Record<string, { icon: React.ReactNode; label: string; accent: string; bg: string; dotColor: string }> = {
    early_accumulation: { icon: <ArrowUpRight className="w-4 h-4" />, label: 'Early Accumulation', accent: 'text-emerald-600', bg: '', dotColor: 'bg-emerald-500' },
    early_distribution: { icon: <ArrowDownRight className="w-4 h-4" />, label: 'Early Distribution', accent: 'text-red-600', bg: '', dotColor: 'bg-red-500' },
    smart_wallet_detected: { icon: <Shield className="w-4 h-4" />, label: 'Smart Wallet', accent: 'text-purple-600', bg: '', dotColor: 'bg-purple-500' },
    cluster_activity: { icon: <Users className="w-4 h-4" />, label: 'Cluster Activity', accent: 'text-blue-600', bg: '', dotColor: 'bg-blue-500' },
  };

  return (
    <div className="rounded-2xl bg-white overflow-hidden" data-testid="radar-block">
      <div className="flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 flex items-center justify-center">
            <Radar className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h3 className="font-bold text-gray-900">Smart Money Events</h3>
            <p className="text-xs text-gray-400">Early activity detected</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-1 p-0.5" data-testid="radar-sort-controls">
            {([['confidence', 'Confidence'], ['net_flow', 'Net Flow'], ['impact', 'Impact'], ['recency', 'Recency']] as const).map(([key, label]) => (
              <button key={key} onClick={() => onSortChange(key)}
                className={`px-3 py-1.5 text-xs font-semibold transition-all ${
                  sortBy === key ? 'text-gray-900' : 'text-gray-400 hover:text-gray-700'
                }`} data-testid={`radar-sort-${key}`}>
                {label}
              </button>
            ))}
          </div>
          <button onClick={onRefresh} disabled={loading}
            className="p-2 text-gray-500 hover:text-gray-700 transition-colors disabled:opacity-50"
            data-testid="radar-refresh-btn">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {loading && events.length === 0 && (
        <div className="py-12 text-center">
          <div className="animate-spin w-6 h-6 border-2 border-gray-900 border-t-transparent rounded-full mx-auto" />
          <p className="text-gray-400 mt-3 text-sm">Scanning for signals...</p>
        </div>
      )}

      {!loading && events.length === 0 && (
        <div className="py-12 text-center">
          <Target className="w-10 h-10 text-gray-200 mx-auto mb-3" />
          <p className="text-gray-400 text-sm">No radar events detected for this window</p>
        </div>
      )}

      <div>
        {events.map((ev, i) => {
          const cfg = eventConfig[ev.event_type] || eventConfig.early_accumulation;
          const isPositive = ev.net_flow_usd > 0;
          const confidenceColor = ev.confidence >= 70 ? 'bg-emerald-500' : ev.confidence >= 50 ? 'bg-amber-500' : 'bg-gray-400';
          const timingColor = ev.timing_score >= 8 ? 'text-emerald-600' : ev.timing_score >= 4 ? 'text-amber-600' : 'text-gray-500';
          const sev = sevConfig[ev.signal_severity] || sevConfig.LOW;
          const scLabel = classConfig[ev.signal_class] || 'Wallet';

          return (
            <div key={`${ev.event_type}-${ev.entity}-${ev.token}-${i}`}
              className="px-6 py-4 hover:bg-gray-50/50 transition-colors group"
              data-testid={`radar-event-${i + 1}`}>
              <div className="flex items-start gap-4">
                <div className={`w-10 h-10 flex items-center justify-center flex-shrink-0 ${cfg.accent}`}>
                  {cfg.icon}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-[10px] font-bold uppercase tracking-wider ${cfg.accent}`}>{cfg.label}</span>
                    {ev.token && <span className="text-[11px] font-bold text-gray-700">{ev.token}</span>}
                    <span className={`text-[9px] font-bold uppercase ${sev.color}`}
                      data-testid={`radar-severity-${i + 1}`}>{ev.signal_severity}</span>
                    <span className="text-[9px] font-semibold text-gray-500 uppercase">{scLabel}</span>
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="font-semibold text-gray-900 text-sm truncate">{ev.entity}</span>
                  </div>
                  {ev.wallet && (
                    <div className="flex items-center gap-2 mt-1">
                      <button onClick={(e) => { e.stopPropagation(); onOpenWallet(ev.wallet); }}
                        className="text-[11px] text-violet-500 hover:text-violet-400 font-mono transition-colors"
                        data-testid={`event-wallet-link-${i}`}>
                        {shortAddr(ev.wallet)}
                      </button>
                      <a href={addressUrl(ev.wallet, chainId)} target="_blank" rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-[10px] text-blue-500 hover:text-blue-700 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <ExternalLink className="w-3 h-3" />{explorerName(chainId)}
                      </a>
                    </div>
                  )}
                  {/* Cluster wallet addresses */}
                  {ev.wallet_addresses?.length > 0 && !ev.wallet && (
                    <EventWalletExpander wallets={ev.wallet_addresses} onOpenWallet={onOpenWallet} chainId={chainId} />
                  )}

                  <div className="flex items-center gap-4 mt-2.5 flex-wrap">
                    <div>
                      <div className="text-[10px] text-gray-400">Net flow</div>
                      <div className={`text-sm font-bold ${isPositive ? 'text-emerald-600' : 'text-red-600'}`}>
                        {isPositive ? '+' : ''}{fmtUsd(ev.net_flow_usd)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-gray-400">Confidence</div>
                      <div className="flex items-center gap-1.5">
                        <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${confidenceColor} transition-all duration-500`}
                            style={{ width: `${ev.confidence}%` }} />
                        </div>
                        <span className="text-xs font-bold text-gray-700">{ev.confidence}%</span>
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-gray-400">Impact</div>
                      <div className="text-sm font-bold text-gray-700">{ev.impact_score}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-gray-400">Timing</div>
                      <div className={`text-sm font-bold ${timingColor}`}>
                        {ev.timing_score > 0 ? '+' : ''}{ev.timing_score}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-gray-400">Last activity</div>
                      <div className="text-xs text-gray-600">{ev.last_activity}</div>
                    </div>
                  </div>

                  {ev.reason.length > 0 && (
                    <div className="mt-3 px-3 py-2">
                      <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-1">Why on radar</div>
                      <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                        {ev.reason.map((r, ri) => (
                          <span key={ri} className="text-[11px] text-gray-600 flex items-center gap-1">
                            <span className={`w-1 h-1 rounded-full ${cfg.dotColor}`} />{r}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex items-center gap-2 mt-3 opacity-0 group-hover:opacity-100 transition-opacity">
                    {ev.wallet && (
                      <button onClick={() => onOpenWallet(ev.wallet)}
                        className="text-[11px] font-semibold text-gray-500 hover:text-gray-900 transition-colors"
                        data-testid={`radar-open-wallet-${i + 1}`}>Open Wallet</button>
                    )}
                    {ev.entity_type !== 'cluster' && (
                      <button onClick={() => onOpenEntity(ev.wallet || ev.entity)}
                        className="text-[11px] font-semibold text-gray-500 hover:text-gray-900 transition-colors"
                        data-testid={`radar-view-entity-${i + 1}`}>View Entity</button>
                    )}
                    {ev.token && (
                      <button onClick={() => { globalThis.window.location.href = `/intelligence/onchain-v3?tab=assets&token=${ev.token}`; }}
                        className="text-[11px] font-semibold text-gray-500 hover:text-gray-900 transition-colors"
                        data-testid={`radar-view-token-${i + 1}`}>View Token</button>
                    )}
                  </div>
                </div>

                <div className="text-right flex-shrink-0">
                  <div className={`text-lg font-bold ${isPositive ? 'text-emerald-600' : 'text-red-600'}`}>
                    {isPositive ? '+' : ''}{fmtUsd(ev.net_flow_usd)}
                  </div>
                  <div className="text-[10px] text-gray-400 mt-0.5">{ev.trades} trades</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}


function EventWalletExpander({ wallets, onOpenWallet, chainId }: { wallets: string[]; onOpenWallet: (addr: string) => void; chainId: number }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="mt-1">
      <button onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
        className="text-[10px] text-violet-500 hover:text-violet-400 transition-colors flex items-center gap-1"
        data-testid="event-expand-wallets">
        {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        {wallets.length} wallets
      </button>
      {expanded && (
        <div className="mt-1.5 space-y-0.5 pl-4">
          {wallets.map((addr, i) => (
            <div key={addr} className="flex items-center gap-2 group/w" data-testid={`event-wallet-${i}`}>
              <button onClick={(e) => { e.stopPropagation(); onOpenWallet(addr); }}
                className="text-[10px] text-violet-400 hover:text-violet-300 font-mono transition-colors">
                {addr.slice(0, 8)}...{addr.slice(-6)}
              </button>
              <a href={addressUrl(addr, chainId)} target="_blank" rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="opacity-0 group-hover/w:opacity-100 transition-opacity">
                <ExternalLink className="w-3 h-3 text-gray-500 hover:text-gray-300" />
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
