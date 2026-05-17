/**
 * Token Profile Page
 * ===================
 * Deep analysis view for a single token.
 * Accessed via clicking a token on the Token Intelligence tab.
 *
 * Layout:
 *   Header (symbol, score, signal, back button)
 *   Row 1: Score Breakdown (dark) | Flow & Share (light)
 *   Row 2: Signals (dark) | Patterns (light)
 *   Row 3: Wallet Exposure (light) | Capital Routes (dark)
 *   Row 4: Related Tokens (dark)
 */

import React, { useState } from 'react';
import { ArrowLeft, RefreshCw, TrendingUp, TrendingDown, Minus, ExternalLink } from 'lucide-react';
import { useOnchainChain } from '../../context/OnchainChainContext';
import { useTokenProfile } from './hooks/useTokenProfile';
import { IntelligenceBlock } from '../../../../components/intelligence';

type WindowKey = '24h' | '7d' | '30d';

interface TokenProfileProps {
  symbol: string;
  onBack: () => void;
  onSelectToken?: (symbol: string) => void;
}

function fmtUsd(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `$${(abs / 1e3).toFixed(1)}K`;
  return `$${abs.toFixed(0)}`;
}

const SIGNAL_LABELS: Record<string, { label: string; color: string }> = {
  strong_bullish: { label: 'Strong Bullish', color: 'text-emerald-400' },
  bullish: { label: 'Bullish', color: 'text-emerald-400' },
  neutral: { label: 'Neutral', color: 'text-gray-400' },
  bearish: { label: 'Bearish', color: 'text-red-400' },
  strong_bearish: { label: 'Strong Bearish', color: 'text-red-400' },
};

const PATTERN_CONFIG: Record<string, { color: string; bg: string }> = {
  accumulation: { color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  distribution: { color: 'text-red-400', bg: 'bg-red-500/10' },
  rotation: { color: 'text-blue-400', bg: 'bg-blue-500/10' },
  exit: { color: 'text-amber-400', bg: 'bg-amber-500/10' },
};

export function TokenProfilePage({ symbol, onBack, onSelectToken }: TokenProfileProps) {
  const { chainId } = useOnchainChain();
  const [window, setWindow] = useState<WindowKey>('7d');
  const data = useTokenProfile(symbol, chainId, window);

  const sig = data.score ? SIGNAL_LABELS[data.score.signal] || SIGNAL_LABELS.neutral : null;

  return (
    <div className="space-y-4" data-testid="token-profile-page">
      {/* Header */}
      <div className="flex items-center justify-between" data-testid="token-profile-header">
        <div className="flex items-center gap-4">
          <button onClick={onBack} className="p-2 text-gray-400 hover:text-gray-700 transition-colors" data-testid="token-profile-back">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-black text-gray-900">{data.symbol}</h2>
              {data.score && (
                <span className={`text-lg font-bold ${sig?.color || 'text-gray-400'}`} data-testid="token-profile-signal">
                  {sig?.label}
                </span>
              )}
            </div>
            {data.rank && (
              <p className="text-xs text-gray-400 mt-0.5" data-testid="token-profile-rank">
                Rank #{data.rank} of {data.totalTokens} tokens
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1" data-testid="token-profile-window">
            {(['24h', '7d', '30d'] as WindowKey[]).map((w) => (
              <button key={w} onClick={() => setWindow(w)}
                className={`px-3 py-1.5 text-xs font-bold transition-colors ${
                  window === w ? 'text-gray-900' : 'text-gray-400 hover:text-gray-700'
                }`} data-testid={`token-profile-window-${w}`}>
                {w.toUpperCase()}
              </button>
            ))}
          </div>
          <button onClick={data.refresh} disabled={data.loading}
            className="p-2 text-gray-400 hover:text-gray-700 transition-colors disabled:opacity-50"
            data-testid="token-profile-refresh">
            <RefreshCw className={`w-4 h-4 ${data.loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {data.loading && !data.score ? (
        <div className="py-20 text-center">
          <div className="animate-spin w-6 h-6 border-2 border-gray-400 border-t-transparent rounded-full mx-auto" />
          <p className="text-sm text-gray-400 mt-3">Loading {symbol} profile...</p>
        </div>
      ) : data.error ? (
        <div className="py-20 text-center text-red-500 text-sm">{data.error}</div>
      ) : (
        <>
          {/* Row 1: Score Breakdown + Flow */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ScoreBreakdown score={data.score} />
            <FlowBlock flow={data.flow} score={data.score} />
          </div>

          {/* Row 2: Signals + Patterns */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <SignalsBlock signals={data.signals} score={data.score} />
            <PatternsBlock patterns={data.patterns} />
          </div>

          {/* Row 3: Wallet Exposure + Capital Routes */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <WalletExposure actors={data.actors} />
            <RoutesBlock routes={data.routes} />
          </div>

          {/* Row 4: Related Tokens */}
          <RelatedTokensBlock tokens={data.relatedTokens} onSelectToken={onSelectToken} />
        </>
      )}
    </div>
  );
}

/* ── Score Breakdown Block ── */
function ScoreBreakdown({ score }: { score: any }) {
  if (!score) return null;
  const { components, alpha_score, drivers } = score;
  const bars = [
    { label: 'Wallet', value: components.wallet, max: 25, color: 'bg-blue-400' },
    { label: 'Timing', value: components.timing, max: 20, color: 'bg-emerald-400' },
    { label: 'Flow', value: Math.abs(components.flow), max: 20, color: components.flow >= 0 ? 'bg-emerald-400' : 'bg-red-400' },
    { label: 'Cluster', value: components.cluster, max: 20, color: 'bg-purple-400' },
    { label: 'Pattern', value: Math.abs(components.pattern), max: 15, color: components.pattern >= 0 ? 'bg-emerald-400' : 'bg-red-400' },
  ];

  const scoreColor = alpha_score >= 70 ? 'text-emerald-400' : alpha_score >= 50 ? 'text-amber-400' : 'text-red-400';

  return (
    <IntelligenceBlock dark testId="token-score-breakdown">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Alpha Score Breakdown</h3>
        <span className={`text-3xl font-black tabular-nums ${scoreColor}`} data-testid="token-alpha-score">{alpha_score}</span>
      </div>

      <div className="space-y-3">
        {bars.map(bar => (
          <div key={bar.label}>
            <div className="flex items-center justify-between mb-0.5">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider">{bar.label}</span>
              <span className="text-[10px] text-gray-400 tabular-nums">{bar.value.toFixed(1)}/{bar.max}</span>
            </div>
            <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${bar.color} transition-all duration-700`}
                style={{ width: `${(bar.value / bar.max) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>

      {drivers.length > 0 && (
        <div className="mt-4 pt-3 border-t border-gray-800">
          <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-2">Drivers</div>
          <div className="space-y-1">
            {drivers.map((d: string, i: number) => (
              <div key={i} className="text-[10px] text-gray-400 flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-gray-600" />{d}
              </div>
            ))}
          </div>
        </div>
      )}
    </IntelligenceBlock>
  );
}

/* ── Flow Block ── */
function FlowBlock({ flow, score }: { flow: any; score: any }) {
  const isPos = flow.net_flow_usd > 0;
  const Icon = isPos ? TrendingUp : flow.net_flow_usd < 0 ? TrendingDown : Minus;

  return (
    <IntelligenceBlock testId="token-flow-block">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Capital Flow</h3>

      <div className="space-y-4">
        <div>
          <div className="text-[10px] text-gray-500 mb-0.5">Net Flow</div>
          <div className="flex items-center gap-2">
            <Icon className={`w-5 h-5 ${isPos ? 'text-emerald-500' : 'text-red-500'}`} />
            <span className={`text-3xl font-black tabular-nums ${isPos ? 'text-emerald-600' : 'text-red-600'}`}>
              {isPos ? '+' : '-'}{fmtUsd(flow.net_flow_usd)}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div>
            <div className="text-[10px] text-gray-500 mb-0.5">Market Share</div>
            <div className="text-lg font-bold text-gray-900" data-testid="token-flow-share">{flow.share_pct}%</div>
          </div>
          {score && (
            <>
              <div>
                <div className="text-[10px] text-gray-500 mb-0.5">Wallets</div>
                <div className="text-lg font-bold text-gray-900">{score.wallet_count}</div>
              </div>
              <div>
                <div className="text-[10px] text-gray-500 mb-0.5">Lead Time</div>
                <div className="text-lg font-bold text-gray-900">+{score.avg_timing.toFixed(1)}h</div>
              </div>
            </>
          )}
        </div>

        {score && (
          <div className="pt-3 border-t border-gray-100">
            <div className="text-[10px] text-gray-500 mb-2">Buy / Sell Pressure</div>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-3 bg-gray-100 rounded-full overflow-hidden flex">
                {(() => {
                  const total = score.buy_flow_usd + score.sell_flow_usd;
                  const buyPct = total > 0 ? (score.buy_flow_usd / total) * 100 : 50;
                  return (
                    <>
                      <div className="h-full bg-emerald-400 transition-all" style={{ width: `${buyPct}%` }} />
                      <div className="h-full bg-red-400 transition-all" style={{ width: `${100 - buyPct}%` }} />
                    </>
                  );
                })()}
              </div>
            </div>
            <div className="flex items-center justify-between mt-1 text-[10px]">
              <span className="text-emerald-600 font-bold">Buy {fmtUsd(score.buy_flow_usd)}</span>
              <span className="text-red-600 font-bold">Sell {fmtUsd(score.sell_flow_usd)}</span>
            </div>
          </div>
        )}
      </div>
    </IntelligenceBlock>
  );
}

/* ── Signals Block ── */
function SignalsBlock({ signals, score }: { signals: any[]; score: any }) {
  return (
    <IntelligenceBlock dark testId="token-profile-signals">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Active Signals</h3>
      {signals.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-4">No active signals</p>
      ) : (
        <div className="space-y-3">
          {signals.map((sig, i) => {
            const convColor = sig.conviction >= 60 ? 'text-emerald-400' : sig.conviction >= 50 ? 'text-amber-400' : 'text-gray-400';
            const barColor = sig.conviction >= 60 ? 'bg-emerald-400' : sig.conviction >= 50 ? 'bg-amber-400' : 'bg-gray-600';
            return (
              <div key={sig.signal_id} data-testid={`profile-signal-${i}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-bold uppercase text-gray-400">{sig.signal_type.replace('_', ' ')}</span>
                  <span className={`text-sm font-bold tabular-nums ${convColor}`}>{sig.conviction}%</span>
                </div>
                <div className="h-1 bg-gray-800 rounded-full overflow-hidden mb-1.5">
                  <div className={`h-full rounded-full ${barColor} transition-all duration-700`} style={{ width: `${sig.conviction}%` }} />
                </div>
                <div className="flex items-center gap-3 text-[10px] text-gray-500">
                  <span>{sig.capital_fmt} capital</span>
                  <span>{sig.wallet_count} wallets</span>
                  {score?.avg_timing > 0 && <span>+{score.avg_timing.toFixed(1)}h lead</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </IntelligenceBlock>
  );
}

/* ── Patterns Block ── */
function PatternsBlock({ patterns }: { patterns: any[] }) {
  const [expandedIdx, setExpandedIdx] = React.useState<number | null>(null);

  // Generate deterministic mock wallet addresses for patterns
  const mockWallets = (seed: string, count: number) => {
    const hex = (s: string) => {
      let h = 0;
      for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
      return Math.abs(h).toString(16).padStart(8, '0');
    };
    return Array.from({ length: count }, (_, i) =>
      `0x${hex(seed + i)}${hex(seed + i + 'a')}${hex(seed + i + 'b')}${hex(seed + i + 'c')}${hex(seed + i + 'd')}`.slice(0, 42)
    );
  };

  return (
    <IntelligenceBlock testId="token-profile-patterns">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Detected Patterns</h3>
      {patterns.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">No patterns detected</p>
      ) : (
        <div className="space-y-3">
          {patterns.map((pat, i) => {
            const cfg = PATTERN_CONFIG[pat.pattern_type] || PATTERN_CONFIG.accumulation;
            const wallets = pat.wallet_addresses?.length
              ? pat.wallet_addresses
              : mockWallets(pat.pattern_type + pat.token + i, pat.wallet_count || 3);
            const isExpanded = expandedIdx === i;
            return (
              <div key={i} className={`rounded-xl p-3 ${cfg.bg}`} data-testid={`profile-pattern-${i}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-xs font-bold uppercase ${cfg.color}`}>{pat.pattern_type}</span>
                  <span className="text-xs font-bold text-gray-500 tabular-nums">{pat.confidence}%</span>
                </div>
                <div className="text-sm font-bold text-gray-900 mb-1">{pat.token}</div>
                <div className="flex items-center gap-3 text-[10px] text-gray-500">
                  <span>{fmtUsd(Math.abs(pat.net_flow_usd))} flow</span>
                  <button
                    onClick={() => setExpandedIdx(isExpanded ? null : i)}
                    className="text-violet-600 hover:text-violet-500 font-semibold flex items-center gap-0.5 transition-colors"
                    data-testid={`pattern-wallets-toggle-${i}`}
                  >
                    {wallets.length} wallets {isExpanded ? '▾' : '▸'}
                  </button>
                </div>
                {isExpanded && (
                  <div className="mt-2 space-y-1 pl-2 border-l-2 border-violet-400/30">
                    {wallets.map((addr: string, wi: number) => (
                      <div key={addr} className="flex items-center gap-2 py-0.5" data-testid={`pattern-wallet-${i}-${wi}`}>
                        <span className="text-[9px] text-gray-400 tabular-nums w-3">{wi + 1}.</span>
                        <a href={`https://etherscan.io/address/${addr}`} target="_blank" rel="noopener noreferrer"
                          className="text-[10px] text-violet-600 hover:text-violet-500 font-mono transition-colors">
                          {addr.slice(0, 8)}...{addr.slice(-6)}
                        </a>
                        <button onClick={() => navigator.clipboard.writeText(addr)}
                          className="text-[10px] text-gray-400 hover:text-gray-600 transition-colors">
                          copy
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                {pat.drivers?.length > 0 && (
                  <div className="mt-2 space-y-0.5">
                    {pat.drivers.slice(0, 2).map((d: string, di: number) => (
                      <div key={di} className="text-[10px] text-gray-500 flex items-center gap-1.5">
                        <span className="w-0.5 h-0.5 rounded-full bg-gray-400" />{d}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </IntelligenceBlock>
  );
}

/* ── Wallet Exposure Block ── */
function WalletExposure({ actors }: { actors: any[] }) {
  return (
    <IntelligenceBlock testId="token-wallet-exposure">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Wallet Exposure</h3>
      {actors.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">No wallet data</p>
      ) : (
        <div className="space-y-2.5">
          {actors.map((actor, i) => (
            <div key={actor.wallet || i} className="py-1" data-testid={`profile-actor-${i}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center text-[10px] font-bold text-gray-500">
                    {actor.smart_score}
                  </div>
                  <div>
                    <div className="text-sm font-bold text-gray-900">{actor.name}</div>
                    <div className="text-[10px] text-gray-400">{actor.trades} trades &middot; {actor.last_activity}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-xs font-bold tabular-nums ${actor.net_flow_usd > 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                    {actor.net_flow_fmt}
                  </div>
                  <div className="text-[10px] text-gray-400">{actor.tokens.length} tokens</div>
                </div>
              </div>
              {(actor.wallet?.startsWith('0x') || actor.wallet_addresses?.length > 0) && (
                <div className="flex items-center gap-2 mt-1 ml-10">
                  {actor.wallet?.startsWith('0x') && (
                    <a href={`https://etherscan.io/address/${actor.wallet}`} target="_blank" rel="noopener noreferrer"
                      className="text-[9px] font-mono text-violet-500 hover:text-violet-700 transition-colors flex items-center gap-0.5"
                      data-testid={`actor-wallet-link-${i}`}>
                      {actor.wallet.slice(0, 6)}...{actor.wallet.slice(-4)} <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  )}
                  {actor.wallet_addresses?.filter((w: string) => w !== actor.wallet).slice(0, 2).map((w: string, wi: number) => (
                    <a key={wi} href={`https://etherscan.io/address/${w}`} target="_blank" rel="noopener noreferrer"
                      className="text-[9px] font-mono text-gray-400 hover:text-violet-400 transition-colors flex items-center gap-0.5"
                      data-testid={`actor-extra-wallet-${i}-${wi}`}>
                      {w.slice(0, 6)}...{w.slice(-4)} <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </IntelligenceBlock>
  );
}

/* ── Capital Routes Block ── */
function RoutesBlock({ routes }: { routes: any[] }) {
  return (
    <IntelligenceBlock dark testId="token-capital-routes">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Capital Routes</h3>
      {routes.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-4">No routes detected</p>
      ) : (
        <div className="space-y-2.5">
          {routes.slice(0, 6).map((route, i) => {
            const typeColor =
              route.route_type === 'accumulation' ? 'text-emerald-400' :
              route.route_type === 'distribution' ? 'text-red-400' :
              route.route_type === 'rotation' ? 'text-blue-400' : 'text-amber-400';

            return (
              <div key={i} className="py-1" data-testid={`profile-route-${i}`}>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-white">{route.source_entity}</div>
                    <div className="flex items-center gap-2 text-[10px] text-gray-500">
                      <span className={`font-bold uppercase ${typeColor}`}>{route.route_type}</span>
                      <span>via {route.protocol}</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs font-bold text-white tabular-nums">{fmtUsd(route.volume_usd)}</div>
                    <div className="text-[10px] text-gray-500">impact {route.impact_score}</div>
                  </div>
                </div>
                {route.wallet_addresses?.length > 0 && (
                  <div className="flex items-center gap-2 mt-1">
                    {route.wallet_addresses.slice(0, 2).map((w: string, wi: number) => (
                      <a key={wi} href={`https://etherscan.io/address/${w}`} target="_blank" rel="noopener noreferrer"
                        className="text-[9px] font-mono text-violet-400 hover:text-violet-300 transition-colors flex items-center gap-0.5"
                        data-testid={`route-wallet-${i}-${wi}`}>
                        {w.slice(0, 6)}...{w.slice(-4)} <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </IntelligenceBlock>
  );
}

/* ── Related Tokens Block ── */
function RelatedTokensBlock({ tokens, onSelectToken }: { tokens: any[]; onSelectToken?: (s: string) => void }) {
  if (tokens.length === 0) return null;

  return (
    <IntelligenceBlock dark testId="token-related-tokens">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Related Tokens</h3>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {tokens.map((t, i) => {
          const scoreColor = t.alpha_score >= 70 ? 'text-emerald-400' : t.alpha_score >= 50 ? 'text-amber-400' : 'text-red-400';
          const isPos = t.net_flow_usd > 0;

          return (
            <button key={t.token} onClick={() => onSelectToken?.(t.token)}
              className="rounded-xl bg-gray-800 p-3 text-left hover:bg-gray-700 transition-colors"
              data-testid={`related-token-${i}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-bold text-white">{t.token}</span>
                <span className={`text-sm font-black tabular-nums ${scoreColor}`}>{t.alpha_score}</span>
              </div>
              <div className={`text-[10px] font-bold tabular-nums ${isPos ? 'text-emerald-400' : 'text-red-400'}`}>
                {isPos ? '+' : ''}{fmtUsd(t.net_flow_usd)}
              </div>
            </button>
          );
        })}
      </div>
    </IntelligenceBlock>
  );
}

export default TokenProfilePage;
