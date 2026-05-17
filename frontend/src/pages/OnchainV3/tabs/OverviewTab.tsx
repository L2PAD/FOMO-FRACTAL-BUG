/**
 * Overview Tab — Market Intelligence Brief (v5 - Final)
 * =====================================================
 * Full dashboard: 11 blocks with Activity Timeline, Whale Monitor,
 * Liquidity Radar, and "View more" navigation links.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  RefreshCw, Zap, ExternalLink, ChevronDown, ChevronUp, ChevronRight,
  ArrowRight, TrendingUp, Anchor, BarChart3,
} from 'lucide-react';
import { IntelligenceBlock } from '../../../components/intelligence';

const API = process.env.REACT_APP_BACKEND_URL;
type Win = '24h' | '7d' | '30d';

function shortAddr(a: string) { return a ? `${a.slice(0, 6)}...${a.slice(-4)}` : ''; }

/* ═══ types ═══ */
interface Summary { active_wallets: number; clusters_detected: number; smart_money_wallets: number; large_transfers: number; transfers_count: number; volume_usd_fmt: string; signals: number; wallet_types: Record<string, number>; }
interface Context { market_bias: string; liquidity_direction: string; exchange_pressure: string; smart_money_activity: string; cluster_activity: string; }
interface Story { sentences: string[]; }
interface Flow { entity: string; inflow_fmt: string; outflow_fmt: string; net_usd: number; net_fmt: string; }
interface FlowTotals { inflow_fmt: string; outflow_fmt: string; net_usd: number; net_fmt: string; }
interface Transfer { token: string; usd_fmt: string; from_label: string; to_label: string; from_addr: string; to_addr: string; tx_type: string; chain: string; time_ago: string; explorer_url: string; }
interface SmartWallet { wallet: string; score: number; label: string; entity: string; volume_fmt: string; last_activity: string; interaction_score: number; early_entry: number; }
interface Entity { entity: string; tx_count: number; volume_usd_fmt: string; entity_type: string; wallet_addresses?: string[]; }
interface Token { token: string; transfer_count: number; volume_fmt: string; }
interface Cluster { cluster_id: string; cluster_name: string; cluster_type: string; cluster_score: number; wallet_count: number; volume_fmt: string; wallets: string[]; }
interface Signal { id: string; title: string; description: string; score: number; severity: string; chain: string; }
interface TimelineBucket { ts: number; label: string; transfers: number; volume_usd: number; volume_fmt: string; signals: number; }
interface WhaleTx { token: string; amount_fmt: string; usd_fmt: string; usd_value: number; from_label: string; to_label: string; from_addr: string; to_addr: string; chain: string; time_ago: string; tx_type: string; }
interface WhaleWallet { address: string; short_addr: string; entity: string; volume_fmt: string; tx_count: number; last_seen: string; }
interface ExDeposit { exchange: string; usd_fmt: string; count: number; }
interface RadarItem { name?: string; chain?: string; token?: string; volume_fmt: string; share_pct: number; tx_count: number; }

function statusColor(v: string, light?: boolean): string {
  const l = v.toLowerCase();
  if (l.includes('high') || l.includes('very active') || l.includes('expanding') || l.includes('accumulation')) return light ? 'text-emerald-600' : 'text-emerald-400';
  if (l.includes('selling') || l.includes('distribution') || l.includes('extreme')) return light ? 'text-red-600' : 'text-red-400';
  if (l.includes('moderate') || l.includes('mild') || l.includes('stable') || l.includes('active')) return light ? 'text-amber-600' : 'text-amber-400';
  return light ? 'text-gray-500' : 'text-gray-400';
}

/* ── ViewMore link ── */
function ViewMore({ tab, label, onNav }: { tab: string; label?: string; onNav: (tab: string) => void }) {
  return (
    <button
      onClick={() => onNav(tab)}
      className="flex items-center gap-1 text-[10px] font-bold text-gray-500 hover:text-white transition-colors"
      data-testid={`view-more-${tab}`}
    >
      {label || 'View more'} <ArrowRight className="w-3 h-3" />
    </button>
  );
}
function ViewMoreLight({ tab, label, onNav }: { tab: string; label?: string; onNav: (tab: string) => void }) {
  return (
    <button
      onClick={() => onNav(tab)}
      className="flex items-center gap-1 text-[10px] font-bold text-gray-400 hover:text-gray-900 transition-colors"
      data-testid={`view-more-${tab}`}
    >
      {label || 'View more'} <ArrowRight className="w-3 h-3" />
    </button>
  );
}

/* ═══════════════════════════════════════════════
   1. NETWORK OVERVIEW (dark)
   ═══════════════════════════════════════════════ */
function HeroBlock({ s }: { s: Summary }) {
  return (
    <IntelligenceBlock dark testId="overview-hero">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] mb-2">Network Overview</div>
          <div className="text-2xl font-black text-violet-400 mb-1" data-testid="overview-wallet-count">{s.active_wallets.toLocaleString()} Wallets Tracked</div>
          <p className="text-xs text-gray-400 mb-4">On-chain intelligence — entities, flows, clusters, smart money</p>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-0.5">
            {Object.entries(s.wallet_types).sort((a, b) => b[1] - a[1]).map(([t, c]) => (
              <div key={t} className="flex items-center justify-between text-[11px]">
                <span className="text-gray-400 capitalize">{t.replace(/_/g, ' ')}</span>
                <span className="text-white font-bold tabular-nums">{c}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-4 lg:gap-8 min-w-0 flex-wrap">
          <div className="text-center"><div className="text-xl lg:text-3xl font-black text-emerald-400 tabular-nums" data-testid="overview-volume">{s.volume_usd_fmt}</div><div className="text-[9px] text-gray-500 uppercase tracking-wider mt-1">Volume</div></div>
          <div className="text-center"><div className="text-xl lg:text-3xl font-black text-cyan-400 tabular-nums">{s.clusters_detected}</div><div className="text-[9px] text-gray-500 uppercase tracking-wider mt-1">Clusters</div></div>
          <div className="text-center"><div className="text-xl lg:text-3xl font-black text-amber-400 tabular-nums">{s.smart_money_wallets}</div><div className="text-[9px] text-gray-500 uppercase tracking-wider mt-1">Smart Money</div></div>
          <div className="text-center"><div className="text-xl lg:text-3xl font-black text-white tabular-nums">{s.transfers_count.toLocaleString()}</div><div className="text-[9px] text-gray-500 uppercase tracking-wider mt-1">Transfers</div></div>
        </div>
      </div>
    </IntelligenceBlock>
  );
}

/* ═══════════════════════════════════════════════
   2. MARKET CONTEXT (light)
   ═══════════════════════════════════════════════ */
function ContextBlock({ ctx }: { ctx: Context }) {
  const items = [
    { label: 'Market Bias', value: ctx.market_bias },
    { label: 'Liquidity', value: ctx.liquidity_direction },
    { label: 'Exchange Pressure', value: ctx.exchange_pressure },
    { label: 'Smart Money', value: ctx.smart_money_activity },
    { label: 'Cluster Activity', value: ctx.cluster_activity },
  ];
  return (
    <IntelligenceBlock testId="market-context">
      <div className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em] mb-4">Market Context</div>
      <div className="grid grid-cols-5 gap-6">
        {items.map(it => (
          <div key={it.label} className="bg-gray-50 rounded-xl px-4 py-3">
            <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">{it.label}</div>
            <div className={`text-sm font-black ${statusColor(it.value, true)}`}>{it.value}</div>
          </div>
        ))}
      </div>
    </IntelligenceBlock>
  );
}

/* ═══════════════════════════════════════════════
   3. MARKET STORY (dark)
   ═══════════════════════════════════════════════ */
function StoryBlock({ story }: { story: Story }) {
  if (!story.sentences.length) return null;
  return (
    <IntelligenceBlock dark testId="market-story">
      <div className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] mb-3">Market Story</div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-8 gap-y-1.5">
        {story.sentences.map((s, i) => (
          <div key={i} className="flex items-start gap-2">
            <span className="text-violet-400 mt-0.5 flex-shrink-0">·</span>
            <p className="text-sm text-gray-300 leading-relaxed">{s}</p>
          </div>
        ))}
      </div>
    </IntelligenceBlock>
  );
}

/* ═══════════════════════════════════════════════
   4. ACTIVITY TIMELINE (light) — NEW
   ═══════════════════════════════════════════════ */
function ActivityTimelineBlock({ buckets, onNav }: { buckets: TimelineBucket[]; onNav: (t: string) => void }) {
  if (!buckets.length) return null;
  const maxTransfers = Math.max(...buckets.map(b => b.transfers), 1);
  const maxVolume = Math.max(...buckets.map(b => b.volume_usd), 1);
  const totalTransfers = buckets.reduce((s, b) => s + b.transfers, 0);
  const totalVolume = buckets.reduce((s, b) => s + b.volume_usd, 0);
  const totalSignals = buckets.reduce((s, b) => s + b.signals, 0);

  return (
    <IntelligenceBlock testId="activity-timeline">
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Activity Timeline</div>
        <ViewMoreLight tab="signals" label="Signals" onNav={onNav} />
      </div>
      {/* Summary stats */}
      <div className="flex items-center gap-4 lg:gap-8 mb-4 flex-wrap">
        <div><span className="text-base lg:text-lg font-black text-emerald-600 tabular-nums">{totalTransfers.toLocaleString()}</span> <span className="text-[9px] text-gray-400 uppercase">transfers</span></div>
        <div><span className="text-base lg:text-lg font-black text-violet-600 tabular-nums">{buckets.find(b => b.volume_usd > 0)?.volume_fmt || '$0'}</span> <span className="text-[9px] text-gray-400 uppercase">volume</span></div>
        <div><span className="text-base lg:text-lg font-black text-amber-600 tabular-nums">{totalSignals}</span> <span className="text-[9px] text-gray-400 uppercase">signals</span></div>
      </div>
      {/* Bar chart */}
      <div className="flex items-end gap-px h-32 overflow-hidden" data-testid="timeline-chart">
        {buckets.map((b, i) => {
          const tH = (b.transfers / maxTransfers) * 100;
          const vH = (b.volume_usd / maxVolume) * 100;
          return (
            <div key={i} className="flex-1 flex flex-col items-stretch justify-end group relative h-full max-w-[80px]" data-testid={`timeline-bar-${i}`}>
              <div className="flex-1 flex flex-col justify-end gap-[1px]">
                <div className="w-full rounded-t bg-emerald-500 transition-all" style={{ height: `${Math.max(tH, b.transfers > 0 ? 6 : 0)}%` }} />
                <div className="w-full rounded-b bg-violet-400 transition-all" style={{ height: `${Math.max(vH * 0.6, b.volume_usd > 0 ? 4 : 0)}%` }} />
              </div>
              {b.signals > 0 && (
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-amber-400" />
              )}
              <div className="text-[8px] text-gray-400 text-center mt-1 truncate">{b.label}</div>
              {/* Tooltip */}
              <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 hidden group-hover:block z-10 bg-gray-900 text-white text-[9px] rounded px-2.5 py-1.5 whitespace-nowrap shadow-lg">
                <div className="font-bold mb-0.5">{b.label}</div>
                <div className="text-emerald-400">{b.transfers.toLocaleString()} transfers</div>
                <div className="text-violet-400">{b.volume_fmt}</div>
                {b.signals > 0 && <div className="text-amber-400">{b.signals} signals</div>}
              </div>
            </div>
          );
        })}
      </div>
      {/* Legend */}
      <div className="flex items-center gap-5 mt-3">
        <div className="flex items-center gap-1.5"><div className="w-2.5 h-2.5 rounded bg-emerald-500" /><span className="text-[9px] text-gray-400">Transfers</span></div>
        <div className="flex items-center gap-1.5"><div className="w-2.5 h-2.5 rounded bg-violet-400" /><span className="text-[9px] text-gray-400">Volume</span></div>
        <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-amber-400" /><span className="text-[9px] text-gray-400">Signals</span></div>
      </div>
    </IntelligenceBlock>
  );
}

/* ═══════════════════════════════════════════════
   5. LIQUIDITY FLOWS (dark)
   ═══════════════════════════════════════════════ */
function LiquidityFlowsBlock({ flows, totals, transfers, onNav }: {
  flows: Flow[]; totals: FlowTotals; transfers: Transfer[]; onNav: (t: string) => void;
}) {
  return (
    <IntelligenceBlock dark testId="liquidity-flows-section">
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Liquidity Flows</div>
        <ViewMore tab="cex-flow" label="CEX Flow" onNav={onNav} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
        <div>
          <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-3">Exchange Flows</div>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div><div className="text-[9px] text-gray-500 uppercase">Inflow</div><div className="text-lg font-black text-emerald-400 tabular-nums">{totals.inflow_fmt}</div></div>
            <div><div className="text-[9px] text-gray-500 uppercase">Outflow</div><div className="text-lg font-black text-red-400 tabular-nums">{totals.outflow_fmt}</div></div>
            <div><div className="text-[9px] text-gray-500 uppercase">Net</div><div className={`text-lg font-black tabular-nums ${totals.net_usd >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{totals.net_fmt}</div></div>
          </div>
          <div className="border-t border-gray-800">
            {flows.slice(0, 5).map(f => (
              <div key={f.entity} className="flex items-center justify-between py-2 border-b border-gray-800/40 last:border-0">
                <span className="text-[11px] text-white font-bold">{f.entity}</span>
                <div className="flex items-center gap-4 tabular-nums">
                  <span className="text-[10px] text-emerald-400 w-14 text-right">{f.inflow_fmt}</span>
                  <span className="text-[10px] text-red-400 w-14 text-right">{f.outflow_fmt}</span>
                  <span className={`text-[10px] font-bold w-14 text-right ${f.net_usd > 0 ? 'text-emerald-400' : f.net_usd < 0 ? 'text-red-400' : 'text-gray-500'}`}>{f.net_fmt}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-3">Large Transfers</div>
          {transfers.slice(0, 6).map((t, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-gray-800/40 last:border-0">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <span className="text-sm font-black text-emerald-400 tabular-nums flex-shrink-0 w-16 text-right">{t.usd_fmt}</span>
                <div className="min-w-0">
                  <div className="text-[11px] text-white font-bold truncate">
                    {t.from_addr ? (
                      <a href={`https://etherscan.io/address/${t.from_addr}`} target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors">{t.from_label}</a>
                    ) : <span>{t.from_label}</span>}
                    <span className="text-gray-500 font-normal"> &rarr; </span>
                    {t.to_addr ? (
                      <a href={`https://etherscan.io/address/${t.to_addr}`} target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors">{t.to_label}</a>
                    ) : <span>{t.to_label}</span>}
                  </div>
                  <div className="text-[10px] text-gray-500">{t.token} · {t.chain} · {t.time_ago}</div>
                </div>
              </div>
              {t.explorer_url && <a href={t.explorer_url} target="_blank" rel="noreferrer" className="text-gray-600 hover:text-gray-400 flex-shrink-0 ml-2"><ExternalLink className="w-3 h-3" /></a>}
            </div>
          ))}
          {transfers.length === 0 && <p className="text-[11px] text-gray-500">No large transfers</p>}
        </div>
      </div>
    </IntelligenceBlock>
  );
}

/* ═══════════════════════════════════════════════
   6. SMART MONEY RADAR (light)
   ═══════════════════════════════════════════════ */
function SmartMoneyRadar({ wallets, onNav }: { wallets: SmartWallet[]; onNav: (t: string) => void }) {
  return (
    <IntelligenceBlock testId="smart-money-section">
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Smart Money Radar</div>
        <ViewMoreLight tab="wallet" label="Wallets" onNav={onNav} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {wallets.slice(0, 6).map((w, i) => (
          <div key={w.wallet} className="bg-gray-50 rounded-xl px-4 py-3.5" data-testid={`smart-money-card-${i}`}>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-sm font-bold text-gray-900">{w.label}</span>
              <span className="text-sm font-black text-amber-500 tabular-nums">{(w.score * 100).toFixed(0)}</span>
            </div>
            <a href={`https://etherscan.io/address/${w.wallet}`} target="_blank" rel="noreferrer"
              className="text-[10px] text-violet-500 hover:text-violet-700 font-bold transition-colors block mb-1.5" data-testid={`smart-money-addr-${i}`}>
              {shortAddr(w.wallet)}
            </a>
            <div className="flex items-center justify-between text-[10px] text-gray-400 mb-1">
              <span>{w.volume_fmt} volume</span>
              <span>{w.last_activity || '-'}</span>
            </div>
            <div className="flex items-center gap-3 text-[10px] text-gray-400">
              <span>{(w.interaction_score * 100).toFixed(0)}% interaction</span>
              <span>{(w.early_entry * 100).toFixed(0)}% early entry</span>
            </div>
          </div>
        ))}
      </div>
      {wallets.length === 0 && <p className="text-sm text-gray-400 text-center py-4">No scored wallets</p>}
    </IntelligenceBlock>
  );
}

/* ═══════════════════════════════════════════════
   7. WHALE MONITOR (dark) — NEW
   ═══════════════════════════════════════════════ */
function WhaleMonitorBlock({ txs, whaleWallets, deposits, withdrawals, onNav }: {
  txs: WhaleTx[]; whaleWallets: WhaleWallet[]; deposits: ExDeposit[]; withdrawals: ExDeposit[]; onNav: (t: string) => void;
}) {
  return (
    <IntelligenceBlock dark testId="whale-monitor">
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Whale Monitor</div>
        <ViewMore tab="entities" label="Entities" onNav={onNav} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Col 1: Top transactions */}
        <div>
          <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-3">Largest Transactions</div>
          {txs.slice(0, 6).map((t, i) => (
            <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-800/40 last:border-0" data-testid={`whale-tx-${i}`}>
              <div className="min-w-0 flex-1">
                <div className="text-[11px] text-white font-bold truncate">
                  {t.from_addr ? (
                    <a href={`https://etherscan.io/address/${t.from_addr}`} target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors">{t.from_label}</a>
                  ) : <span>{t.from_label}</span>}
                  <span className="text-gray-600"> &rarr; </span>
                  {t.to_addr ? (
                    <a href={`https://etherscan.io/address/${t.to_addr}`} target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors">{t.to_label}</a>
                  ) : <span>{t.to_label}</span>}
                </div>
                <div className="text-[9px] text-gray-500">{t.token} · {t.chain} · {t.time_ago}</div>
              </div>
              <span className="text-[11px] font-black text-emerald-400 tabular-nums ml-2">{t.usd_fmt}</span>
            </div>
          ))}
          {txs.length === 0 && <p className="text-[10px] text-gray-600">No whale transactions</p>}
        </div>
        {/* Col 2: Top whale wallets */}
        <div>
          <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-3">Top Whale Wallets</div>
          {whaleWallets.slice(0, 6).map((w, i) => (
            <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-800/40 last:border-0" data-testid={`whale-wallet-${i}`}>
              <div className="min-w-0">
                <a href={`https://etherscan.io/address/${w.address}`} target="_blank" rel="noreferrer"
                  className="text-[11px] text-violet-400 hover:text-violet-300 font-bold transition-colors">{w.short_addr}</a>
                {w.entity && <span className="text-[9px] text-gray-500 ml-1.5">{w.entity}</span>}
              </div>
              <div className="flex items-center gap-3 tabular-nums ml-2">
                <span className="text-[10px] text-gray-400">{w.tx_count} tx</span>
                <span className="text-[10px] text-white font-bold">{w.volume_fmt}</span>
              </div>
            </div>
          ))}
        </div>
        {/* Col 3: Exchange deposits/withdrawals */}
        <div>
          <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-3">Exchange Deposits</div>
          {deposits.slice(0, 3).map((d, i) => (
            <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-800/40 last:border-0">
              <span className="text-[11px] text-white font-bold">{d.exchange}</span>
              <span className="text-[10px] text-red-400 font-bold tabular-nums">{d.usd_fmt}</span>
            </div>
          ))}
          <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-3 mt-4">Exchange Withdrawals</div>
          {withdrawals.slice(0, 3).map((d, i) => (
            <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-800/40 last:border-0">
              <span className="text-[11px] text-white font-bold">{d.exchange}</span>
              <span className="text-[10px] text-emerald-400 font-bold tabular-nums">{d.usd_fmt}</span>
            </div>
          ))}
        </div>
      </div>
    </IntelligenceBlock>
  );
}

/* ═══════════════════════════════════════════════
   8. NETWORK ACTIVITY (dark)
   ═══════════════════════════════════════════════ */
function NetworkActivityBlock({ entities, tokens, onNav }: { entities: Entity[]; tokens: Token[]; onNav: (t: string) => void }) {
  const [expandedEntity, setExpandedEntity] = useState<string | null>(null);
  return (
    <IntelligenceBlock dark testId="network-activity-section">
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Network Activity</div>
        <ViewMore tab="entities" label="Entities" onNav={onNav} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
        <div>
          <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-3">Top Entities</div>
          {entities.slice(0, 6).map((e, i) => {
            const hasWallets = e.wallet_addresses && e.wallet_addresses.length > 0;
            const isExpanded = expandedEntity === e.entity;
            return (
              <div key={e.entity} data-testid={`entity-row-${i}`}>
                <div
                  className={`flex items-center justify-between py-2 border-b border-gray-800/40 last:border-0 ${hasWallets ? 'cursor-pointer hover:bg-gray-800/30 -mx-2 px-2 rounded' : ''}`}
                  onClick={() => hasWallets && setExpandedEntity(isExpanded ? null : e.entity)}
                >
                  <div className="flex items-center gap-2">
                    {hasWallets && (isExpanded
                      ? <ChevronDown className="w-3 h-3 text-gray-500" />
                      : <ChevronRight className="w-3 h-3 text-gray-500" />
                    )}
                    <span className="text-[10px] text-gray-500 tabular-nums w-4">{i + 1}</span>
                    <span className="text-[11px] text-white font-bold">{e.entity}</span>
                    <span className="text-[9px] text-gray-500 capitalize">{e.entity_type}</span>
                  </div>
                  <div className="flex items-center gap-4 tabular-nums">
                    <span className="text-[10px] text-gray-400">{e.tx_count.toLocaleString()} tx</span>
                    <span className="text-[10px] text-white font-bold">{e.volume_usd_fmt}</span>
                  </div>
                </div>
                {isExpanded && e.wallet_addresses && (
                  <div className="pl-6 pb-2 space-y-0.5 border-l-2 border-violet-500/20 ml-3 mt-1" data-testid={`entity-wallets-${i}`}>
                    {e.wallet_addresses.map((addr, wi) => (
                      <div key={addr} className="flex items-center gap-2 py-0.5 group/ew">
                        <span className="text-[9px] text-gray-600 tabular-nums w-3">{wi + 1}.</span>
                        <a href={`https://etherscan.io/address/${addr}`} target="_blank" rel="noopener noreferrer"
                          className="text-[10px] text-violet-400 font-mono hover:underline">
                          {shortAddr(addr)}
                        </a>
                        <a href={`https://etherscan.io/address/${addr}`} target="_blank" rel="noopener noreferrer"
                          className="opacity-0 group-hover/ew:opacity-100 transition-opacity">
                          <ExternalLink className="w-2.5 h-2.5 text-gray-500 hover:text-blue-400" />
                        </a>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <div>
          <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-3">Top Tokens</div>
          {tokens.slice(0, 6).map(t => (
            <div key={t.token} className="flex items-center justify-between py-2 border-b border-gray-800/40 last:border-0" data-testid={`token-row-${t.token}`}>
              <span className="text-[11px] text-white font-bold">{t.token}</span>
              <div className="flex items-center gap-4 tabular-nums">
                <span className="text-[10px] text-gray-400">{t.transfer_count} tx</span>
                <span className="text-[10px] text-white font-bold">{t.volume_fmt}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </IntelligenceBlock>
  );
}

/* ═══════════════════════════════════════════════
   9. LIQUIDITY RADAR (light) — NEW
   ═══════════════════════════════════════════════ */
function LiquidityRadarBlock({ byExchange, byChain, byToken, onNav }: {
  byExchange: RadarItem[]; byChain: RadarItem[]; byToken: RadarItem[]; onNav: (t: string) => void;
}) {
  return (
    <IntelligenceBlock testId="liquidity-radar">
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Liquidity Radar</div>
        <ViewMoreLight tab="cex-flow" label="CEX Flow" onNav={onNav} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* By Exchange */}
        <div>
          <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-3">By Exchange</div>
          {byExchange.slice(0, 5).map((e, i) => (
            <div key={i} className="mb-2" data-testid={`radar-exchange-${i}`}>
              <div className="flex items-center justify-between text-[11px] mb-0.5">
                <span className="font-bold text-gray-900">{e.name}</span>
                <span className="text-gray-500 tabular-nums">{e.volume_fmt} · {e.share_pct}%</span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-violet-500 rounded-full transition-all" style={{ width: `${Math.min(e.share_pct, 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
        {/* By Chain */}
        <div>
          <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-3">By Chain</div>
          {byChain.slice(0, 5).map((c, i) => (
            <div key={i} className="mb-2" data-testid={`radar-chain-${i}`}>
              <div className="flex items-center justify-between text-[11px] mb-0.5">
                <span className="font-bold text-gray-900 capitalize">{c.chain}</span>
                <span className="text-gray-500 tabular-nums">{c.volume_fmt} · {c.share_pct}%</span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-cyan-500 rounded-full transition-all" style={{ width: `${Math.min(c.share_pct, 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
        {/* By Token */}
        <div>
          <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-3">By Token</div>
          {byToken.slice(0, 5).map((t, i) => (
            <div key={i} className="mb-2" data-testid={`radar-token-${i}`}>
              <div className="flex items-center justify-between text-[11px] mb-0.5">
                <span className="font-bold text-gray-900">{t.token}</span>
                <span className="text-gray-500 tabular-nums">{t.volume_fmt} · {t.share_pct}%</span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full transition-all" style={{ width: `${Math.min(t.share_pct, 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </IntelligenceBlock>
  );
}

/* ═══════════════════════════════════════════════
   10. CLUSTER INTELLIGENCE (light)
   ═══════════════════════════════════════════════ */
function ClusterIntelBlock({ clusters, onNav }: { clusters: Cluster[]; onNav: (t: string) => void }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  return (
    <div data-testid="cluster-intelligence-section">
      <IntelligenceBlock>
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Cluster Intelligence</div>
          <ViewMoreLight tab="actors" label="Actors" onNav={onNav} />
        </div>
        {clusters.slice(0, 5).map(c => {
          const isOpen = expanded === c.cluster_id;
          return (
            <div key={c.cluster_id} className="border-b border-gray-100 last:border-0" data-testid={`cluster-row-${c.cluster_id}`}>
              <div className="flex items-center justify-between py-2.5 cursor-pointer" onClick={() => setExpanded(isOpen ? null : c.cluster_id)}>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-bold text-violet-600">{c.cluster_name}</span>
                </div>
                <div className="flex items-center gap-5">
                  <span className="text-xs text-gray-900 font-bold tabular-nums">{c.wallet_count} wallets</span>
                  <span className="text-xs text-gray-900 font-bold tabular-nums">{c.volume_fmt}</span>
                  <span className={`text-xs font-black tabular-nums ${c.cluster_score >= 0.4 ? 'text-amber-500' : 'text-gray-400'}`}>{(c.cluster_score * 100).toFixed(0)}</span>
                  {isOpen ? <ChevronUp className="w-3.5 h-3.5 text-gray-400" /> : <ChevronDown className="w-3.5 h-3.5 text-gray-400" />}
                </div>
              </div>
              {isOpen && c.wallets.length > 0 && (
                <div className="pb-3 pl-3 grid grid-cols-2 md:grid-cols-4 gap-1.5">
                  {c.wallets.map(w => (
                    <a key={w} href={`https://etherscan.io/address/${w}`} target="_blank" rel="noreferrer"
                      className="text-[11px] text-violet-500 hover:text-violet-700 transition-colors cursor-pointer">
                      {shortAddr(w)}
                    </a>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        {clusters.length === 0 && <p className="text-sm text-gray-400 text-center py-4">No cluster data</p>}
      </IntelligenceBlock>
    </div>
  );
}

/* ═══════════════════════════════════════════════
   11. KEY SIGNALS (dark)
   ═══════════════════════════════════════════════ */
function KeySignalsBlock({ signals, onNav }: { signals: Signal[]; onNav: (t: string) => void }) {
  return (
    <div data-testid="key-signals-section">
      <IntelligenceBlock dark>
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Key Signals</div>
          <ViewMore tab="signals" label="Terminal" onNav={onNav} />
        </div>
        <div className="border-t border-gray-800">
          {signals.slice(0, 5).map((s, i) => {
            const sc = s.severity === 'EXTREME' ? 'text-red-400' : s.severity === 'STRONG' ? 'text-amber-400' : 'text-gray-400';
            return (
              <div key={s.id || i} className="flex items-center justify-between py-2.5 border-b border-gray-800/40 last:border-0" data-testid={`signal-row-${i}`}>
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <Zap className={`w-3 h-3 flex-shrink-0 ${sc}`} />
                  <div className="min-w-0">
                    <span className={`text-[11px] font-bold ${sc}`}>{s.title}</span>
                    <span className="text-[9px] text-gray-600 ml-1.5">{s.chain}</span>
                    <div className="text-[10px] text-gray-500 truncate">{s.description}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                  <span className={`text-sm font-black tabular-nums ${sc}`}>{s.score}</span>
                  <span className={`text-[9px] font-bold uppercase ${sc}`}>{s.severity}</span>
                </div>
              </div>
            );
          })}
          {signals.length === 0 && <p className="text-sm text-gray-400 text-center py-4">No signals</p>}
        </div>
      </IntelligenceBlock>
    </div>
  );
}

/* ═══════════════════════════════════════════════
   MAIN
   ═══════════════════════════════════════════════ */
export function OverviewTab({ onNavigate }: { onNavigate?: (tab: string) => void }) {
  const nav = onNavigate || (() => {});
  const [win, setWin] = useState<Win>('30d');
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [context, setContext] = useState<Context | null>(null);
  const [story, setStory] = useState<Story | null>(null);
  const [flows, setFlows] = useState<Flow[]>([]);
  const [flowTotals, setFlowTotals] = useState<FlowTotals>({ inflow_fmt: '$0', outflow_fmt: '$0', net_usd: 0, net_fmt: '$0' });
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [smartMoney, setSmartMoney] = useState<SmartWallet[]>([]);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [tokens, setTokens] = useState<Token[]>([]);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [timeline, setTimeline] = useState<TimelineBucket[]>([]);
  const [whaleTxs, setWhaleTxs] = useState<WhaleTx[]>([]);
  const [whaleWallets, setWhaleWallets] = useState<WhaleWallet[]>([]);
  const [deposits, setDeposits] = useState<ExDeposit[]>([]);
  const [withdrawals, setWithdrawals] = useState<ExDeposit[]>([]);
  const [radarExchange, setRadarExchange] = useState<RadarItem[]>([]);
  const [radarChain, setRadarChain] = useState<RadarItem[]>([]);
  const [radarToken, setRadarToken] = useState<RadarItem[]>([]);

  const fetchAll = useCallback(async (w: Win) => {
    setLoading(true);
    try {
      const q = `window=${w}`;
      const [sumR, ctxR, stR, flowR, trR, smR, entR, tokR, clR, sigR, tlR, whR, rdR] = await Promise.all([
        fetch(`${API}/api/onchain-overview/summary?${q}`).then(r => r.json()),
        fetch(`${API}/api/onchain-overview/context?${q}`).then(r => r.json()),
        fetch(`${API}/api/onchain-overview/story?${q}`).then(r => r.json()),
        fetch(`${API}/api/onchain-overview/exchange-flows?${q}`).then(r => r.json()),
        fetch(`${API}/api/onchain-overview/transfers?${q}&limit=8`).then(r => r.json()),
        fetch(`${API}/api/onchain-overview/smart-money?${q}&limit=9`).then(r => r.json()),
        fetch(`${API}/api/onchain-overview/entities?${q}&limit=8`).then(r => r.json()),
        fetch(`${API}/api/onchain-overview/token-flows?${q}`).then(r => r.json()),
        fetch(`${API}/api/onchain-overview/clusters?${q}&limit=8`).then(r => r.json()),
        fetch(`${API}/api/onchain-overview/signals?limit=10`).then(r => r.json()),
        fetch(`${API}/api/onchain-overview/timeline?${q}`).then(r => r.json()),
        fetch(`${API}/api/onchain-overview/whales?${q}&limit=10`).then(r => r.json()),
        fetch(`${API}/api/onchain-overview/radar?${q}`).then(r => r.json()),
      ]);
      if (sumR.ok) setSummary(sumR);
      if (ctxR.ok) setContext(ctxR);
      if (stR.ok) setStory(stR);
      if (flowR.ok) { setFlows(flowR.flows || []); setFlowTotals(flowR.totals || { inflow_fmt: '$0', outflow_fmt: '$0', net_usd: 0, net_fmt: '$0' }); }
      if (trR.ok) setTransfers(trR.transfers || []);
      if (smR.ok) setSmartMoney(smR.wallets || []);
      if (entR.ok) setEntities(entR.entities || []);
      if (tokR.ok) setTokens(tokR.tokens || []);
      if (clR.ok) setClusters(clR.clusters || []);
      if (sigR.ok) setSignals(sigR.signals || []);
      if (tlR.ok) setTimeline(tlR.buckets || []);
      if (whR.ok) { setWhaleTxs(whR.top_transactions || []); setWhaleWallets(whR.whale_wallets || []); setDeposits(whR.deposits || []); setWithdrawals(whR.withdrawals || []); }
      if (rdR.ok) { setRadarExchange(rdR.by_exchange || []); setRadarChain(rdR.by_chain || []); setRadarToken(rdR.by_token || []); }
    } catch (e) { console.error('Overview fetch error:', e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(win); }, [fetchAll, win]);

  if (loading && !summary) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="overview-loading">
        <div className="animate-spin w-5 h-5 border-2 border-violet-400 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="overview-tab">
      {/* Time filter + refresh */}
      <div className="flex items-center justify-end gap-3">
        <div className="flex items-center gap-1">
          {(['24h', '7d', '30d'] as Win[]).map(w => (
            <button key={w} onClick={() => setWin(w)}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-colors ${win === w ? 'bg-gray-900 text-white' : 'text-gray-400 hover:text-gray-700 hover:bg-gray-100'}`}
              data-testid={`overview-window-${w}`}>
              {w.toUpperCase()}
            </button>
          ))}
        </div>
        <button onClick={() => fetchAll(win)} disabled={loading}
          className="p-2 text-gray-400 hover:text-gray-700 transition-colors disabled:opacity-50"
          data-testid="overview-refresh-btn">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* 1. NETWORK OVERVIEW (dark) */}
      {summary && <HeroBlock s={summary} />}

      {/* 2. MARKET CONTEXT (light) */}
      {context && <ContextBlock ctx={context} />}

      {/* 3. MARKET STORY (dark) */}
      {story && <StoryBlock story={story} />}

      {/* 4. ACTIVITY TIMELINE (light) — NEW */}
      {timeline.length > 0 && <ActivityTimelineBlock buckets={timeline} onNav={nav} />}

      {/* 5. LIQUIDITY FLOWS (dark) */}
      <LiquidityFlowsBlock flows={flows} totals={flowTotals} transfers={transfers} onNav={nav} />

      {/* 6. SMART MONEY RADAR (light) */}
      <SmartMoneyRadar wallets={smartMoney} onNav={nav} />

      {/* 7. WHALE MONITOR (dark) — NEW */}
      <WhaleMonitorBlock txs={whaleTxs} whaleWallets={whaleWallets} deposits={deposits} withdrawals={withdrawals} onNav={nav} />

      {/* 8. NETWORK ACTIVITY (dark) */}
      <NetworkActivityBlock entities={entities} tokens={tokens} onNav={nav} />

      {/* 9. LIQUIDITY RADAR (light) — NEW */}
      <LiquidityRadarBlock byExchange={radarExchange} byChain={radarChain} byToken={radarToken} onNav={nav} />

      {/* 10+11. CLUSTER INTELLIGENCE + KEY SIGNALS (side by side) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ClusterIntelBlock clusters={clusters} onNav={nav} />
        <KeySignalsBlock signals={signals} onNav={nav} />
      </div>
    </div>
  );
}

export default OverviewTab;
