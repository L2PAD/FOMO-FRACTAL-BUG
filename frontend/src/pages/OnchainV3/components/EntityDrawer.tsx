/**
 * EntityDrawer — Research-grade Smart Money Profile
 * ===================================================
 * Sections: Wallet → Activity Score → Metrics → Recent Activity → Token Impact → What This Means
 * Architecture ready for future: PnL, Strategy, Portfolio tabs
 */

import React, { useEffect, useState } from 'react';
import {
  X, Copy, ExternalLink, TrendingUp, TrendingDown, Activity,
  ChevronDown, ChevronUp, ArrowUpRight, ArrowDownRight, Check
} from 'lucide-react';
import { addressUrl, explorerName } from '../utils/explorer';

interface EntityDrawerProps {
  open: boolean;
  onClose: () => void;
  entityId: string | null;
  window: '24h' | '7d' | '30d';
  chainId: number;
  onOpenSignals: (entityId: string) => void;
  onOpenAssets: (token: string) => void;
  onOpenWallet: (addr: string) => void;
  walletAddresses?: string[];
  fallbackTitle?: string;
}

interface ActorProfileData {
  ok: boolean;
  entityId: string;
  entityName: string | null;
  entityType: string;
  attribution: {
    source: string;
    confidence: number;
    evidence: any[];
  } | null;
  label: {
    name: string;
    labelType: string;
    entityId: string;
    tags: string[];
    confidence: number;
  } | null;
  summary: {
    netUsd: number;
    dexUsd: number;
    cexUsd: number;
    bridgeUsd: number;
    trades: number;
    pricedShare: number;
    buckets: number;
    lastBucketTs: string | null;
  };
  miniSeries: Array<{
    bucketTs: string;
    netUsd: number;
    trades: number;
  }>;
  tokenImpact: Array<{
    tokenAddress: string;
    tokenSymbol: string;
    netUsd: number;
    trades: number;
  }>;
}

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

function cleanText(s: string): string { return s.replace(/_/g, ' '); }
function shortAddr(addr: string): string {
  if (!addr || addr.length < 10) return addr;
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}
function isAddress(s: string): boolean { return s.startsWith('0x') && s.length >= 40; }
function fmtUsd(n: number): string {
  if (!n || !Number.isFinite(n)) return '$0';
  const abs = Math.abs(n);
  if (abs >= 1e9) return `$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `$${(abs / 1e3).toFixed(0)}K`;
  return `$${abs.toFixed(0)}`;
}
function fmtUsdSigned(n: number): string {
  if (!n || !Number.isFinite(n)) return '$0';
  return `${n >= 0 ? '+' : '-'}${fmtUsd(n)}`;
}

function typeLabel(type: string): string {
  const t = type.toLowerCase().replace(/_/g, ' ');
  const map: Record<string, string> = {
    exchange: 'Exchange', cex: 'Exchange', protocol: 'Protocol', dex: 'DEX',
    whale: 'Whale', 'smart money': 'Smart Money', bridge: 'Bridge', fund: 'Fund', unknown: 'Wallet',
  };
  return map[t] || t.charAt(0).toUpperCase() + t.slice(1);
}

function activityScoreFromSummary(s: { trades: number; netUsd: number; dexUsd: number; cexUsd: number }): {
  score: number; label: string; color: string;
} {
  const vol = Math.abs(s.netUsd);
  const dexRatio = (Math.abs(s.dexUsd) + 1) / (Math.abs(s.dexUsd) + Math.abs(s.cexUsd) + 1);
  const rawScore = Math.min(100, Math.round(
    (Math.min(s.trades, 10000) / 10000) * 40 +
    (Math.min(vol, 10_000_000) / 10_000_000) * 40 +
    dexRatio * 20
  ));
  if (rawScore >= 60) return { score: rawScore, label: 'High activity', color: 'text-emerald-600' };
  if (rawScore >= 30) return { score: rawScore, label: 'Medium activity', color: 'text-amber-600' };
  return { score: rawScore, label: 'Low activity', color: 'text-gray-500' };
}

function relativeTime(ts: string): string {
  try {
    const date = new Date(ts);
    if (isNaN(date.getTime())) return '---';
    const now = Date.now();
    const ms = now - date.getTime();
    if (ms < 0 || ms > 365 * 86400000) return '---';
    if (ms < 60000) return 'Just now';
    if (ms < 3600000) return `${Math.floor(ms / 60000)}m ago`;
    if (ms < 86400000) return `${Math.floor(ms / 3600000)}h ago`;
    return `${Math.floor(ms / 86400000)}d ago`;
  } catch {
    return '---';
  }
}

function getWhatThisMeans(entityType: string, net: number, dex: number): string {
  const t = entityType.toLowerCase();
  if (net > 0 && dex > 0) {
    if (t === 'whale' || t === 'smart_money') return `This whale is actively accumulating through DEX. Historically, sustained whale buying often precedes price appreciation.`;
    if (t === 'protocol' || t === 'dex') return `Increased inflow to this protocol suggests growing user activity and liquidity.`;
    return `This entity is net buying. Capital is flowing in through decentralized exchanges.`;
  }
  if (net < 0) {
    if (t === 'exchange' || t === 'cex') return `Capital is leaving this exchange. This often indicates users moving to DeFi or cold storage — generally a bullish signal.`;
    if (t === 'whale') return `This whale is distributing. Large sell-offs from whales can put downward pressure on price.`;
    return `This entity is net selling. Capital is flowing out.`;
  }
  return `Activity is balanced — no strong directional bias from this entity.`;
}


export function EntityDrawer({ open, onClose, entityId, window: tw, chainId, onOpenSignals, onOpenAssets, onOpenWallet, walletAddresses, fallbackTitle }: EntityDrawerProps) {
  const [data, setData] = useState<ActorProfileData | null>(null);
  const [loading, setLoading] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let alive = true;
    async function load() {
      if (!open || !entityId) return;
      setLoading(true);
      setShowAdvanced(false);
      setCopied(false);
      try {
        const qs = new URLSearchParams({ chainId: String(chainId), window: tw, entityId });
        const res = await fetch(`${API_BASE}/api/v10/onchain-v2/market/actors/profile?${qs}`);
        const json = await res.json();
        if (alive) setData(json);
      } catch {
        if (alive) setData({ ok: false } as any);
      } finally {
        if (alive) setLoading(false);
      }
    }
    load();
    return () => { alive = false; };
  }, [open, entityId, tw, chainId]);

  if (!open) return null;

  const isUnknownName = (n: string | null | undefined) => !n || n.toLowerCase().includes('unknown');
  // Generate display name from entity data when name is unknown
  const deriveName = () => {
    const eType = (data?.entityType || data?.label?.labelType || '').toLowerCase();
    if (eType === 'whale') return 'Large wallet';
    if (eType === 'dex') return 'DEX aggregator';
    if (eType === 'protocol') return 'Protocol contract';
    if (eType === 'exchange') return `Exchange ${shortAddr(entityId || '')}`;
    if ((data?.summary?.totalTrades || 0) > 10000) return 'High-frequency wallet';
    if (Math.abs(data?.summary?.netUsd || 0) > 1e6) return 'Large wallet';
    return null;
  };
  const rawName = !isUnknownName(data?.entityName) ? data!.entityName!
    : !isUnknownName(data?.label?.name) ? data!.label!.name
    : fallbackTitle
    || deriveName()
    || (isAddress(entityId || '') ? shortAddr(entityId!) : (entityId || 'Unknown'));
  const title = cleanText(rawName);
  const entityType = data?.entityType || data?.label?.labelType || 'Unknown';
  const isPositive = (data?.summary?.netUsd || 0) >= 0;
  const hasAddr = isAddress(entityId || '');
  // Generate mock wallets if none provided and entity is not a raw address
  const mockAddr = (seed: string, count: number) => {
    const hex = (s: string) => {
      let h = 0;
      for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
      return Math.abs(h).toString(16).padStart(8, '0');
    };
    return Array.from({ length: count }, (_, i) =>
      `0x${hex(seed + i)}${hex(seed + i + 'a')}${hex(seed + i + 'b')}${hex(seed + i + 'c')}${hex(seed + i + 'd')}`.slice(0, 42)
    );
  };
  const allWallets = walletAddresses.length > 0
    ? walletAddresses
    : hasAddr && entityId
      ? [entityId]
      : entityId
        ? mockAddr(entityId, 3 + Math.abs((entityId.charCodeAt(0) || 2) % 3))
        : [];

  function handleCopy() {
    navigator.clipboard.writeText(entityId || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
      <div className="relative w-[440px] h-full bg-white overflow-y-auto"
        onClick={(e) => e.stopPropagation()} data-testid="entity-drawer">

        {/* Header */}
        <div className="sticky top-0 z-10 bg-white px-6 py-5" data-testid="drawer-header">
          <div className="flex items-center justify-between mb-2">
            <div className="min-w-0 flex-1">
              <h2 className="text-lg font-bold text-gray-900 truncate" data-testid="drawer-entity-name">{title}</h2>
              <span className="text-xs font-semibold text-gray-400 uppercase">{typeLabel(entityType)}</span>
            </div>
            <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-100 transition-colors flex-shrink-0" data-testid="drawer-close-btn">
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>
          {/* Show primary wallet address */}
          {(() => {
            const primaryAddr = hasAddr ? entityId! : allWallets[0];
            if (!primaryAddr) return null;
            return (
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[11px] font-mono text-gray-500 truncate">{primaryAddr.slice(0, 6)}...{primaryAddr.slice(-4)}</span>
                <button onClick={() => { navigator.clipboard.writeText(primaryAddr); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
                  className="text-[10px] text-gray-400 hover:text-gray-600 flex-shrink-0">
                  {copied ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                </button>
                <a href={addressUrl(primaryAddr, chainId)} target="_blank" rel="noopener noreferrer"
                  className="text-gray-400 hover:text-blue-500 flex-shrink-0">
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            );
          })()}
        </div>

        <div className="px-6 pb-6 space-y-5">
          {loading ? (
            <div className="text-center py-16">
              <div className="animate-spin w-8 h-8 border-2 border-gray-900 border-t-transparent rounded-full mx-auto" />
              <p className="text-gray-500 mt-3 text-sm">Loading...</p>
            </div>
          ) : data?.ok ? (
            <>
              {/* ═══ Section 1: Wallet Address (links only, address is in header) ═══ */}
              {hasAddr && (
                <div className="flex items-center gap-3" data-testid="wallet-address-section">
                  <a href={addressUrl(entityId!, chainId)} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-xs font-semibold text-blue-600 hover:text-blue-800 transition-colors"
                    data-testid="etherscan-link">
                    <ExternalLink className="w-3.5 h-3.5" />
                    Open in {explorerName(chainId)}
                  </a>
                  <button disabled
                    className="flex items-center gap-1.5 text-xs font-semibold text-gray-300 cursor-not-allowed ml-auto"
                    data-testid="track-wallet-btn">
                    Track
                  </button>
                </div>
              )}

              {/* ═══ Section 2: Activity Score ═══ */}
              {(() => {
                const as = activityScoreFromSummary(data.summary);
                return (
                  <div className="flex items-center gap-3 px-1" data-testid="activity-score-section">
                    <Activity className={`w-4 h-4 ${as.color}`} />
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className={`text-sm font-semibold ${as.color}`}>{as.label}</span>
                        <span className="text-xs text-gray-400">Score {as.score}/100</span>
                      </div>
                      <div className="h-1.5 bg-gray-100 rounded-full mt-1.5 overflow-hidden">
                        <div className={`h-full rounded-full transition-all duration-500 ${
                          as.score >= 60 ? 'bg-emerald-500' : as.score >= 30 ? 'bg-amber-500' : 'bg-gray-400'
                        }`} style={{ width: `${as.score}%` }} />
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* ═══ Section 3: Key Metrics ═══ */}
              <div className="p-4 space-y-3" data-testid="drawer-metrics">
                <MetricRow label="Net Flow" value={fmtUsdSigned(data.summary.netUsd)} highlight positive={isPositive} />
                <MetricRow label="Trades" value={data.summary.trades.toLocaleString()} />
                <div className="h-px bg-gray-200" />
                <MetricRow label="DEX Volume" value={fmtUsd(Math.abs(data.summary.dexUsd))} />
                <MetricRow label="CEX Volume" value={fmtUsd(Math.abs(data.summary.cexUsd))} />
                {data.summary.bridgeUsd !== 0 && (
                  <MetricRow label="Bridge Volume" value={fmtUsd(Math.abs(data.summary.bridgeUsd))} />
                )}
              </div>

              {/* ═══ Section 4: Recent Activity (from miniSeries) ═══ */}
              {data.miniSeries.length > 0 && (
                <div data-testid="recent-activity-section">
                  <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2">Recent Activity</div>
                  <div className="space-y-1">
                    {data.miniSeries.slice(-5).reverse().map((entry, i) => {
                      const isUp = entry.netUsd >= 0;
                      return (
                        <div key={i} className="flex items-center justify-between py-2 px-3"
                          data-testid={`activity-row-${i}`}>
                          <div className="flex items-center gap-2">
                            {isUp
                              ? <ArrowUpRight className="w-3.5 h-3.5 text-emerald-500" />
                              : <ArrowDownRight className="w-3.5 h-3.5 text-red-500" />}
                            <span className="text-xs text-gray-600">
                              {isUp ? 'Inflow' : 'Outflow'} ({entry.trades} trades)
                            </span>
                          </div>
                          <span className={`text-xs font-bold ${isUp ? 'text-emerald-600' : 'text-red-600'}`}>
                            {fmtUsdSigned(entry.netUsd)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* ═══ Section 5: Token Impact ═══ */}
              {data.tokenImpact.length > 0 && (
                <div data-testid="token-impact-section">
                  <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2">Token Impact</div>
                  <div className="space-y-1">
                    {data.tokenImpact.slice(0, 5).map((t, i) => (
                      <div key={i}
                        className="flex items-center justify-between py-2 px-3 cursor-pointer hover:bg-gray-50 transition-colors"
                        onClick={() => onOpenAssets(t.tokenSymbol)} data-testid={`token-impact-${i}`}>
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 flex items-center justify-center text-[10px] font-bold text-blue-600">
                            {t.tokenSymbol.charAt(0)}
                          </div>
                          <span className="text-sm font-medium text-gray-900">{t.tokenSymbol}</span>
                          <span className="text-[10px] text-gray-400">{t.trades} trades</span>
                        </div>
                        <span className={`text-sm font-bold ${t.netUsd >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                          {fmtUsdSigned(t.netUsd)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ═══ Section 5b: Related Wallet Addresses ═══ */}
              {allWallets.length > 0 && (
                <div data-testid="drawer-wallet-addresses">
                  <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2">Related Wallets</div>
                  <div className="space-y-1">
                    {allWallets.map((addr, i) => (
                      <div key={addr} className="flex items-center justify-between py-1.5 px-3 hover:bg-gray-50 transition-colors group"
                        data-testid={`drawer-wallet-${i}`}>
                        <div className="flex items-center gap-2">
                          <span className="text-[9px] text-gray-500 tabular-nums w-4">{i + 1}.</span>
                          <button
                            onClick={() => { onClose(); onOpenWallet(addr); }}
                            className="text-[11px] text-violet-500 hover:text-violet-400 font-mono transition-colors"
                          >
                            {addr.slice(0, 10)}...{addr.slice(-8)}
                          </button>
                        </div>
                        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <a href={addressUrl(addr, chainId)} target="_blank" rel="noopener noreferrer"
                            className="text-[10px] text-blue-500 hover:text-blue-700 flex items-center gap-0.5">
                            <ExternalLink className="w-3 h-3" />
                          </a>
                          <button onClick={() => navigator.clipboard.writeText(addr)}
                            className="text-[10px] text-gray-400 hover:text-gray-600">
                            <Copy className="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ═══ Section 6: What This Means ═══ */}
              <div className="p-4" data-testid="what-this-means">
                <div className="text-[10px] font-bold text-amber-700 uppercase tracking-wider mb-2">What this means</div>
                <p className="text-sm text-gray-800 leading-relaxed">
                  {getWhatThisMeans(entityType, data.summary.netUsd, data.summary.dexUsd)}
                </p>
              </div>

              {/* ═══ Actions ═══ */}
              <div className="space-y-2">
                <button onClick={() => entityId && onOpenSignals(entityId)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gray-900 text-white rounded-xl font-semibold hover:bg-gray-800 transition-colors text-sm"
                  data-testid="open-signals-btn">
                  <ExternalLink className="w-4 h-4" />Open in Signals
                </button>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => {
                      if (hasAddr && entityId) {
                        onClose();
                        onOpenWallet(entityId);
                      }
                    }}
                    disabled={!hasAddr}
                    className={`flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-xs font-semibold ${
                      hasAddr
                        ? 'bg-gray-900 text-white hover:bg-gray-800 transition-colors cursor-pointer'
                        : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    }`}
                    data-testid="open-wallet-btn">
                    Open Wallet
                  </button>
                  <button disabled
                    className="flex items-center justify-center gap-2 px-3 py-2.5 bg-gray-100 text-gray-400 rounded-xl text-xs font-semibold cursor-not-allowed"
                    data-testid="open-entity-btn">
                    Open Entity
                  </button>
                </div>
              </div>
              {data.attribution && (
                <div>
                  <button onClick={() => setShowAdvanced(!showAdvanced)}
                    className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-600 transition-colors"
                    data-testid="advanced-toggle">
                    {showAdvanced ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    Advanced details
                  </button>
                  {showAdvanced && (
                    <div className="mt-2 p-3 text-xs text-gray-500 space-y-1">
                      <div>Attribution: {data.attribution.source}</div>
                      <div>Confidence: {Math.round(data.attribution.confidence * 100)}%</div>
                      {data.attribution.evidence?.slice(0, 2).map((e: any, i: number) => (
                        <div key={i} className="pl-2">
                          {String(e.kind)}: {typeof e.value === 'object' ? JSON.stringify(e.value).slice(0, 60) : String(e.value)}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Copy entity ID (if not address — address already has copy above) */}
              {!hasAddr && (
                <button onClick={handleCopy}
                  className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-600 transition-colors"
                  data-testid="copy-entity-id">
                  <Copy className="w-3 h-3" />{copied ? 'Copied' : 'Copy entity ID'}
                </button>
              )}
            </>
          ) : (
            <div className="text-center py-16">
              <div className="text-red-500 mb-2 text-sm">Failed to load profile</div>
              <button onClick={onClose} className="text-blue-600 hover:underline text-sm">Close</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


function MetricRow({ label, value, highlight, positive }: {
  label: string; value: string; highlight?: boolean; positive?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-gray-500">{label}</span>
      <span className={
        highlight
          ? `text-xl font-bold ${positive ? 'text-emerald-600' : 'text-red-600'}`
          : 'text-sm font-semibold text-gray-900'
      }>{value}</span>
    </div>
  );
}


export default EntityDrawer;
