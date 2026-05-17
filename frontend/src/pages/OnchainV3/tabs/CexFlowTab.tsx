/**
 * CEX Flow Tab v2.2 — Exchange Market Intelligence
 * =====================================================
 * Sprint B: 3 new intelligence engines
 *
 * Layout:
 *   HERO: CEX Market Bias
 *   Row 1: Liquidity Shock | Exchange Pressure | Stablecoin Power
 *   Row 2: Exchange Inventory | Market Liquidity Map | Exchange Flows
 *   Row 3: Flow Composition | Largest Transfers | Pump/Dump Setup
 *   Row 4: Exchange Rotation
 */

import React, { useState } from 'react';
import {
  RefreshCw, ArrowRight, TrendingUp, TrendingDown, Minus,
  Activity, Droplets, Shield, ChevronRight, ChevronDown, Zap, Package, Layers, ArrowUpRight, ArrowDownRight,
  ExternalLink, Copy, Check,
} from 'lucide-react';
import { useOnchainChain } from '../context/OnchainChainContext';
import {
  useCexIntelligence,
  ExchangePressure, StablecoinPower, ExchangeFlow,
  LargestTransfer, ExchangeRotation, RotationFallback,
  PumpSetup, Indicators, MarketLiquidity,
  ExchangeInventoryItem, FlowClassification, LiquidityShock,
  BehaviorMap, LiquidityEngine,
  HeroDominantVenue, HeroDominantAsset,
  TransactionRef,
} from './cex/useCexIntelligence';
import { IntelligenceBlock } from '../../../components/intelligence';
import { txUrl, addressUrl } from '../utils/explorer';

type WindowKey = '24h' | '7d' | '30d';

function fmtUsd(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `$${(abs / 1e3).toFixed(1)}K`;
  return `$${abs.toFixed(0)}`;
}

const shortAddr = (a: string) => a ? `${a.slice(0, 6)}...${a.slice(-4)}` : '';
const shortHash = (h: string) => h ? `${h.slice(0, 8)}...${h.slice(-4)}` : '';

function TxRefList({ txs, chainId, dark }: { txs: TransactionRef[]; chainId: number; dark?: boolean }) {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  if (!txs?.length) return null;
  const textPrimary = dark ? 'text-violet-400' : 'text-violet-500';
  const textSecondary = dark ? 'text-gray-500' : 'text-gray-400';
  return (
    <div className="mt-2 space-y-1 pl-2 border-l-2 border-violet-500/20" data-testid="tx-ref-list">
      {txs.map((tx, i) => (
        <div key={tx.tx_hash || i} className="flex items-center gap-2 flex-wrap group/tx py-0.5" data-testid={`tx-ref-${i}`}>
          {tx.direction && (
            <span className={`text-[8px] font-bold px-1 py-0.5 rounded ${tx.direction === 'deposit' ? 'text-red-400 bg-red-500/10' : 'text-emerald-400 bg-emerald-500/10'}`}>
              {tx.direction === 'deposit' ? 'IN' : 'OUT'}
            </span>
          )}
          {tx.usd_fmt && <span className={`text-[10px] font-bold ${dark ? 'text-white' : 'text-gray-900'} tabular-nums`}>{tx.usd_fmt}</span>}
          {tx.from_address && (
            <a href={addressUrl(tx.from_address, chainId)} target="_blank" rel="noopener noreferrer"
              className={`text-[10px] ${textPrimary} font-mono hover:underline`}>
              {shortAddr(tx.from_address)}
            </a>
          )}
          {tx.from_address && tx.to_address && <ArrowRight className="w-2.5 h-2.5 text-gray-500 flex-shrink-0" />}
          {tx.to_address && (
            <a href={addressUrl(tx.to_address, chainId)} target="_blank" rel="noopener noreferrer"
              className={`text-[10px] ${textPrimary} font-mono hover:underline`}>
              {shortAddr(tx.to_address)}
            </a>
          )}
          {tx.tx_hash && (
            <a href={txUrl(tx.tx_hash, chainId)} target="_blank" rel="noopener noreferrer"
              className={`text-[9px] ${textSecondary} hover:text-blue-400 flex items-center gap-0.5`}
              data-testid={`tx-hash-link-${i}`}>
              <ExternalLink className="w-2.5 h-2.5" />tx
            </a>
          )}
          {tx.from_address && (
            <button className="opacity-0 group-hover/tx:opacity-100 transition-opacity"
              onClick={() => { navigator.clipboard.writeText(tx.from_address); setCopiedIdx(i); setTimeout(() => setCopiedIdx(null), 1500); }}>
              {copiedIdx === i ? <Check className="w-2.5 h-2.5 text-emerald-400" /> : <Copy className="w-2.5 h-2.5 text-gray-500" />}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

function WalletList({ wallets, chainId, dark }: { wallets: string[]; chainId: number; dark?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  if (!wallets?.length) return null;
  const textPrimary = dark ? 'text-violet-400' : 'text-violet-500';
  return (
    <div className="mt-1">
      <button onClick={() => setExpanded(!expanded)}
        className={`text-[10px] ${textPrimary} hover:opacity-80 font-semibold flex items-center gap-0.5 transition-colors`}
        data-testid="cex-wallet-expand">
        {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        {wallets.length} wallets
      </button>
      {expanded && (
        <div className="mt-1 space-y-0.5 pl-2 border-l-2 border-violet-500/20">
          {wallets.map((addr, i) => (
            <div key={addr} className="flex items-center gap-2 py-0.5 group/w" data-testid={`cex-wallet-${i}`}>
              <span className={`text-[9px] ${dark ? 'text-gray-500' : 'text-gray-400'} tabular-nums w-4`}>{i + 1}.</span>
              <a href={addressUrl(addr, chainId)} target="_blank" rel="noopener noreferrer"
                className={`text-[10px] ${textPrimary} font-mono hover:underline`}>
                {shortAddr(addr)}
              </a>
              <a href={addressUrl(addr, chainId)} target="_blank" rel="noopener noreferrer"
                className="opacity-0 group-hover/w:opacity-100 transition-opacity">
                <ExternalLink className="w-2.5 h-2.5 text-gray-500 hover:text-blue-400" />
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface CexFlowProps {
  onNavigateTab?: (tab: string, params?: Record<string, string>) => void;
}

export function CexFlowTab({ onNavigateTab }: CexFlowProps) {
  const { chainId } = useOnchainChain();
  const [window, setWindow] = useState<WindowKey>('30d');
  const data = useCexIntelligence(chainId, window);

  return (
    <div className="space-y-4" data-testid="cex-flow-tab">
      {/* Header */}
      <div className="flex items-center justify-end gap-3" data-testid="cex-header">
        <div className="flex items-center gap-1">
          {(['24h', '7d', '30d'] as WindowKey[]).map((w) => (
            <button key={w} onClick={() => setWindow(w)}
              className={`px-3 py-1.5 text-xs font-bold transition-colors ${
                window === w ? 'text-gray-900' : 'text-gray-400 hover:text-gray-700'
              }`} data-testid={`cex-window-${w}`}>
              {w.toUpperCase()}
            </button>
          ))}
        </div>
        <button onClick={data.refresh} disabled={data.loading}
          className="p-2 text-gray-400 hover:text-gray-700 transition-colors disabled:opacity-50"
          data-testid="cex-refresh">
          <RefreshCw className={`w-4 h-4 ${data.loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Error state */}
      {data.error && !data.loading && (
        <IntelligenceBlock dark testId="cex-error">
          <div className="flex items-center justify-between py-4">
            <div>
              <div className="text-sm font-bold text-red-400 mb-1">Failed to load CEX data</div>
              <p className="text-xs text-gray-500">{data.error}</p>
            </div>
            <button onClick={data.refresh}
              className="px-3 py-1.5 text-xs font-bold text-white bg-gray-800 rounded hover:bg-gray-700 transition-colors"
              data-testid="cex-retry">Retry</button>
          </div>
        </IntelligenceBlock>
      )}

      {/* HERO: Market Bias */}
      <CexMarketBias
        bias={data.market_bias} confidence={data.confidence}
        pressure={data.exchange_pressure} narrativeLines={data.narrative_lines}
        drivers={data.drivers} offsetting={data.offsetting_factors}
        indicators={data.indicators} loading={data.loading}
        dominantVenue={data.dominant_venue} dominantAsset={data.dominant_asset}
      />

      {/* Row 1: Liquidity Shock | Exchange Pressure | Stablecoin Power */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <LiquidityShockBlock shock={data.liquidity_shock} loading={data.loading} chainId={chainId} />
        <ExchangePressureBlock pressure={data.exchange_pressure} loading={data.loading} chainId={chainId} />
        <StablecoinPowerBlock power={data.stablecoin_power} loading={data.loading} chainId={chainId} />
      </div>

      {/* Row 2: Exchange Inventory | Exchange Behavior Map | Market Liquidity Map */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ExchangeInventoryBlock inventory={data.exchange_inventory} loading={data.loading} chainId={chainId} />
        <ExchangeBehaviorMapBlock behaviorMap={data.behavior_map} loading={data.loading} />
        <MarketLiquidityMapBlock liquidity={data.market_liquidity} loading={data.loading} />
      </div>

      {/* Row 3: Flow Composition | Exchange Flows | Largest Transfers */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <FlowCompositionBlock classification={data.flow_classification} loading={data.loading} chainId={chainId} />
        <ExchangeFlowsBlock exchanges={data.top_exchanges} loading={data.loading} chainId={chainId} />
        <LargestTransfersBlock transfers={data.largest_transfers} loading={data.loading} chainId={chainId} />
      </div>

      {/* Row 4: Pump/Dump Setup | Exchange Rotation */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PumpSetupBlock setups={data.pump_setups} loading={data.loading} chainId={chainId} />
        <ExchangeRotationBlock
          rotations={data.exchange_rotation}
          fallback={data.rotation_fallback}
          loading={data.loading}
        />
      </div>
    </div>
  );
}

/* ── Shared ── */
function Skeleton({ dark }: { dark?: boolean }) {
  return (
    <IntelligenceBlock dark={dark} testId="cex-skeleton">
      <div className="flex items-center justify-center py-10">
        <div className={`animate-spin w-5 h-5 border-2 ${dark ? 'border-emerald-400' : 'border-gray-400'} border-t-transparent rounded-full`} />
      </div>
    </IntelligenceBlock>
  );
}

function IndicatorGauge({ label, value, icon: Icon, color }: {
  label: string; value: number; icon: React.ElementType; color: string;
}) {
  return (
    <div className="flex items-center gap-2.5" data-testid={`cex-indicator-${label.toLowerCase().replace(' ', '-')}`}>
      <Icon className={`w-3.5 h-3.5 ${color}`} />
      <div className="flex-1">
        <div className="flex items-center justify-between mb-0.5">
          <span className="text-[9px] font-bold text-gray-500 uppercase tracking-wider">{label}</span>
          <span className={`text-[10px] font-black tabular-nums ${color}`}>{value}%</span>
        </div>
        <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
          <div className={`h-full rounded-full transition-all duration-700 ${
            value >= 65 ? 'bg-red-400' : value >= 40 ? 'bg-amber-400' : 'bg-emerald-400'
          }`} style={{ width: `${value}%` }} />
        </div>
      </div>
    </div>
  );
}


/* ══════════════════════════════════════════════════════════
   HERO: CEX Market Bias
   ══════════════════════════════════════════════════════════ */
function CexMarketBias({ bias, confidence, pressure, narrativeLines, drivers, offsetting, indicators, loading, dominantVenue, dominantAsset }: {
  bias: string; confidence: string; pressure: ExchangePressure | null;
  narrativeLines: string[]; drivers: string[]; offsetting: string[];
  indicators: Indicators | null; loading: boolean;
  dominantVenue: HeroDominantVenue | null; dominantAsset: HeroDominantAsset | null;
}) {
  if (loading && !pressure) return <Skeleton dark />;
  const bc = { bullish: { label: 'BULLISH LIQUIDITY', color: 'text-emerald-400' }, bearish: { label: 'SELL PRESSURE', color: 'text-red-400' }, neutral: { label: 'NEUTRAL FLOW', color: 'text-gray-400' } }[bias] || { label: 'NEUTRAL FLOW', color: 'text-gray-400' };
  const confColor = confidence === 'high' ? 'text-emerald-400' : confidence === 'moderate' ? 'text-amber-400' : 'text-gray-500';

  return (
    <IntelligenceBlock dark testId="cex-market-bias">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] mb-2">CEX Market Bias</div>
          <div className={`text-2xl font-black mb-3 ${bc.color}`} data-testid="cex-bias-label">{bc.label}</div>
          {narrativeLines.length > 0 && (
            <div className="space-y-1 mb-4">
              {narrativeLines.map((line, i) => (
                <p key={i} className={`${i === 0 ? 'text-sm font-medium text-white' : 'text-xs text-gray-400'} leading-relaxed`}
                  data-testid={`cex-narrative-${i}`}>{line}</p>
              ))}
            </div>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
            {drivers.length > 0 && (
              <div data-testid="cex-drivers">
                <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-1.5">Drivers</div>
                <div className="space-y-1">
                  {drivers.map((d, i) => (
                    <div key={i} className="text-[11px] text-gray-300 flex items-start gap-1.5">
                      <span className="w-1 h-1 rounded-full bg-red-400 mt-1.5 flex-shrink-0" />{d}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {offsetting.length > 0 && (
              <div data-testid="cex-offsetting">
                <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-1.5">Offsetting Factors</div>
                <div className="space-y-1">
                  {offsetting.map((o, i) => (
                    <div key={i} className="text-[11px] text-gray-400 flex items-start gap-1.5">
                      <span className="w-1 h-1 rounded-full bg-emerald-400 mt-1.5 flex-shrink-0" />{o}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          {/* Dominant Venue + Dominant Asset (Sprint A Polish) */}
          {(dominantVenue || dominantAsset) && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4" data-testid="cex-hero-dominants">
              {dominantVenue && (
                <div className="bg-gray-800/40 rounded-lg px-3 py-2" data-testid="cex-hero-dominant-venue">
                  <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-1">Dominant Venue</div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-black text-white">{dominantVenue.exchange}</span>
                    <span className={`text-[10px] font-bold tabular-nums ${dominantVenue.bias === 'accumulation' ? 'text-emerald-400' : dominantVenue.bias === 'sell_pressure' ? 'text-red-400' : 'text-gray-400'}`}>
                      {dominantVenue.net_fmt}
                    </span>
                  </div>
                  <div className="text-[9px] text-gray-500 mt-0.5">{dominantVenue.volume_fmt} &middot; {dominantVenue.share}% market share</div>
                </div>
              )}
              {dominantAsset && (
                <div className="bg-gray-800/40 rounded-lg px-3 py-2" data-testid="cex-hero-dominant-asset">
                  <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-1">Dominant Asset</div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-black text-white">{dominantAsset.token}</span>
                    <span className={`text-[10px] font-bold tabular-nums ${dominantAsset.bias === 'accumulation' ? 'text-emerald-400' : dominantAsset.bias === 'sell_pressure' ? 'text-red-400' : 'text-gray-400'}`}>
                      {dominantAsset.net_fmt}
                    </span>
                  </div>
                  <div className="text-[9px] text-gray-500 mt-0.5">{dominantAsset.volume_fmt} &middot; {dominantAsset.share}% of flow</div>
                </div>
              )}
            </div>
          )}
          {indicators && (
            <div className="space-y-2 pt-3 border-t border-gray-800" data-testid="cex-indicators">
              <IndicatorGauge label="Sell Pressure" value={indicators.sell_pressure} icon={Activity} color="text-red-400" />
              <IndicatorGauge label="Liquidity" value={indicators.liquidity} icon={Droplets} color="text-blue-400" />
              <IndicatorGauge label="Confidence" value={indicators.confidence} icon={Shield} color="text-emerald-400" />
            </div>
          )}
        </div>
        {pressure && (
          <div className="lg:w-56 lg:border-l lg:border-gray-800 lg:pl-6 space-y-2.5 flex-shrink-0">
            <div>
              <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-0.5">Deposits</div>
              <div className="text-lg font-black text-red-400 tabular-nums" data-testid="cex-deposits">{pressure.deposits_fmt}</div>
            </div>
            <div>
              <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-0.5">Withdrawals</div>
              <div className="text-lg font-black text-emerald-400 tabular-nums" data-testid="cex-withdrawals">{pressure.withdrawals_fmt}</div>
            </div>
            <div>
              <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-0.5">Net Flow</div>
              <div className={`text-lg font-black tabular-nums ${pressure.net_flow >= 0 ? 'text-red-400' : 'text-emerald-400'}`}
                data-testid="cex-net-flow">{pressure.net_fmt}</div>
            </div>
            <div className="pt-2 border-t border-gray-800">
              <div className="flex items-center gap-2">
                <span className="text-[9px] font-bold text-gray-500 uppercase tracking-wider">Confidence</span>
                <span className={`text-xs font-black uppercase ${confColor}`} data-testid="cex-confidence">{confidence}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </IntelligenceBlock>
  );
}


/* ══════════════════════════════════════════════════════════
   LIQUIDITY SHOCK DETECTOR (Sprint B)
   ══════════════════════════════════════════════════════════ */
function LiquidityShockBlock({ shock, loading, chainId }: { shock: LiquidityShock | null; loading: boolean; chainId: number }) {
  if (loading && !shock) return <Skeleton dark />;
  if (!shock) return null;

  const stateColors: Record<string, { bg: string; text: string; border: string }> = {
    strong_bullish_shock: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/30' },
    bullish_imbalance: { bg: 'bg-emerald-500/5', text: 'text-emerald-400', border: 'border-emerald-500/20' },
    neutral: { bg: 'bg-gray-500/5', text: 'text-gray-400', border: 'border-gray-500/20' },
    bearish_imbalance: { bg: 'bg-red-500/5', text: 'text-red-400', border: 'border-red-500/20' },
    strong_bearish_shock: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/30' },
  };
  const sc = stateColors[shock.state] || stateColors.neutral;

  return (
    <IntelligenceBlock dark testId="cex-liquidity-shock">
      <div className="flex items-center gap-2 mb-3">
        <Zap className={`w-4 h-4 ${sc.text}`} />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Liquidity Shock</h3>
      </div>

      {/* State label */}
      <div className={`rounded-lg px-3 py-2 mb-3 border ${sc.bg} ${sc.border}`}>
        <div className={`text-sm font-black ${sc.text}`} data-testid="cex-shock-label">{shock.label}</div>
        <div className="text-[10px] text-gray-400 mt-0.5">{shock.interpretation}</div>
      </div>

      {/* Buy vs Sell */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <div className="text-[9px] text-gray-500 uppercase tracking-wider">Buy Power</div>
          <div className="text-lg font-black text-emerald-400 tabular-nums" data-testid="cex-shock-buy">{shock.buy_power_fmt}</div>
        </div>
        <div>
          <div className="text-[9px] text-gray-500 uppercase tracking-wider">Sell Supply</div>
          <div className="text-lg font-black text-red-400 tabular-nums" data-testid="cex-shock-sell">{shock.sell_supply_fmt}</div>
        </div>
      </div>

      {/* Net */}
      <div className="flex items-center justify-between mb-3 py-1.5 border-t border-gray-800">
        <span className="text-[9px] text-gray-500 uppercase tracking-wider">Net</span>
        <span className={`text-sm font-black tabular-nums ${sc.text}`} data-testid="cex-shock-net">{shock.net_fmt}</span>
      </div>

      {/* Drivers */}
      {shock.drivers.length > 0 && (
        <div className="space-y-0.5">
          {shock.drivers.map((d, i) => (
            <div key={i} className="text-[10px] text-gray-400 flex items-center gap-1.5">
              <ChevronRight className="w-2.5 h-2.5 text-gray-600" />{d}
            </div>
          ))}
        </div>
      )}

      {/* Exchange drivers */}
      {shock.exchange_drivers.length > 0 && (
        <div className="mt-2 pt-2 border-t border-gray-800 space-y-1">
          {shock.exchange_drivers.slice(0, 3).map((ed, i) => (
            <div key={i}>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-gray-400">{ed.exchange}</span>
                <div className="flex items-center gap-1.5">
                  <span className={`font-bold tabular-nums ${ed.contribution >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {ed.contribution_fmt}
                  </span>
                  <span className="text-gray-600">{ed.dominant_factor}</span>
                </div>
              </div>
              {ed.wallet_addresses && ed.wallet_addresses.length > 0 && (
                <WalletList wallets={ed.wallet_addresses} chainId={chainId} dark />
              )}
            </div>
          ))}
        </div>
      )}
    </IntelligenceBlock>
  );
}


/* ══════════════════════════════════════════════════════════
   EXCHANGE INVENTORY (Sprint B)
   ══════════════════════════════════════════════════════════ */
function ExchangeInventoryBlock({ inventory, loading, chainId }: { inventory: ExchangeInventoryItem[]; loading: boolean; chainId: number }) {
  if (loading && inventory.length === 0) return <Skeleton />;

  const stateColors: Record<string, string> = {
    growing: 'text-red-600 bg-red-50',
    shrinking: 'text-emerald-600 bg-emerald-50',
    stable: 'text-gray-600 bg-gray-100',
  };

  return (
    <IntelligenceBlock testId="cex-inventory">
      <div className="flex items-center gap-2 mb-4">
        <Package className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Exchange Inventory</h3>
      </div>

      {inventory.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">No inventory data</p>
      ) : (
        <div className="space-y-4">
          {inventory.map((item, idx) => (
            <div key={item.token} data-testid={`cex-inventory-${idx}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-bold text-gray-900">{item.token}</span>
                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${stateColors[item.state] || stateColors.stable}`}>
                  {item.state === 'growing' ? 'GROWING' : item.state === 'shrinking' ? 'SHRINKING' : 'STABLE'}
                </span>
              </div>

              {/* Deposits vs Withdrawals */}
              <div className="grid grid-cols-2 gap-2 mb-1.5">
                <div>
                  <div className="text-[9px] text-gray-400 uppercase">Deposits</div>
                  <div className="text-xs font-bold text-red-600 tabular-nums">{item.deposits_fmt}</div>
                </div>
                <div>
                  <div className="text-[9px] text-gray-400 uppercase">Withdrawals</div>
                  <div className="text-xs font-bold text-emerald-600 tabular-nums">{item.withdrawals_fmt}</div>
                </div>
              </div>

              {/* Net change */}
              <div className="flex items-center justify-between mb-1">
                <span className="text-[9px] text-gray-400">Net Change</span>
                <span className={`text-xs font-black tabular-nums ${item.net_change >= 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                  {item.net_change_fmt} ({item.change_pct > 0 ? '+' : ''}{item.change_pct}%)
                </span>
              </div>

              <div className="text-[10px] text-gray-500 italic">{item.interpretation}</div>

              {/* Per exchange */}
              {item.per_exchange.length > 0 && (
                <div className="mt-2 pt-1.5 border-t border-gray-100 space-y-0.5">
                  {item.per_exchange.slice(0, 3).map((pe, i) => (
                    <div key={i} className="flex items-center justify-between text-[10px]">
                      <span className="text-gray-500">{pe.exchange}</span>
                      <span className={`font-bold tabular-nums ${pe.net >= 0 ? 'text-red-500' : 'text-emerald-500'}`}>
                        {pe.net >= 0 ? '+' : ''}{pe.net_fmt}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Top transactions */}
              {item.top_transactions && item.top_transactions.length > 0 && (
                <TxRefList txs={item.top_transactions} chainId={chainId} />
              )}
            </div>
          ))}
        </div>
      )}
    </IntelligenceBlock>
  );
}


/* ══════════════════════════════════════════════════════════
   EXCHANGE BEHAVIOR MAP (Sprint C)
   ══════════════════════════════════════════════════════════ */
function ExchangeBehaviorMapBlock({ behaviorMap, loading }: { behaviorMap: BehaviorMap | null; loading: boolean }) {
  if (loading && !behaviorMap) return <Skeleton />;
  if (!behaviorMap || behaviorMap.points.length === 0) return null;

  const quadrantColors: Record<string, { dot: string; text: string; bg: string; border: string }> = {
    accumulation: { dot: 'bg-emerald-500', text: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-300' },
    distribution: { dot: 'bg-red-500', text: 'text-red-600', bg: 'bg-red-50', border: 'border-red-300' },
    liquidity_hub: { dot: 'bg-blue-500', text: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-300' },
    neutral: { dot: 'bg-gray-400', text: 'text-gray-600', bg: 'bg-gray-100', border: 'border-gray-300' },
  };

  const maxVol = Math.max(...behaviorMap.points.map(p => p.volume), 1);

  return (
    <IntelligenceBlock testId="cex-behavior-map">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em] mb-3">Exchange Behavior Map</h3>

      {/* Quadrant visualization — overflow visible for tooltips */}
      <div className="relative w-full aspect-square bg-gray-50 rounded-lg mb-3 border border-gray-100" data-testid="cex-behavior-quadrant">
        {/* Quadrant background tints */}
        <div className="absolute top-0 left-0 w-1/2 h-1/2 bg-emerald-500/[0.03] rounded-tl-lg" />
        <div className="absolute top-0 right-0 w-1/2 h-1/2 bg-blue-500/[0.03] rounded-tr-lg" />
        <div className="absolute bottom-0 right-0 w-1/2 h-1/2 bg-red-500/[0.03] rounded-br-lg" />

        {/* Axis lines */}
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-200/70" />
        <div className="absolute top-1/2 left-0 right-0 h-px bg-gray-200/70" />

        {/* Quadrant labels — inside corners, smaller and subtler */}
        <div className="absolute top-2 left-2 text-[7px] font-bold text-emerald-400/60 uppercase pointer-events-none">Accumulation</div>
        <div className="absolute top-2 right-2 text-[7px] font-bold text-blue-400/60 uppercase pointer-events-none">Liquidity Hub</div>
        <div className="absolute bottom-2 left-2 text-[7px] font-bold text-gray-400/60 uppercase pointer-events-none">Neutral</div>
        <div className="absolute bottom-2 right-2 text-[7px] font-bold text-red-400/60 uppercase pointer-events-none">Distribution</div>

        {/* Exchange dots — NO permanent labels, only hover tooltip */}
        {behaviorMap.points.map((p) => {
          const qc = quadrantColors[p.quadrant] || quadrantColors.neutral;
          const left = 12 + p.x * 76;
          const top = 12 + (1 - (p.y + 1) / 2) * 76;
          const size = Math.max(16, Math.min(36, (p.volume / maxVol) * 36));
          return (
            <div key={p.entity_id} className="absolute group z-10"
              style={{ left: `${left}%`, top: `${top}%`, transform: 'translate(-50%, -50%)' }}
              data-testid={`cex-behavior-dot-${p.entity_id}`}>
              {/* Dot with initial letter */}
              <div className={`rounded-full ${qc.dot} border-2 border-white shadow-md transition-all duration-200 hover:scale-[1.6] hover:z-20 flex items-center justify-center cursor-pointer`}
                style={{ width: `${size}px`, height: `${size}px` }}>
                <span className="text-white font-black" style={{ fontSize: `${Math.max(7, size * 0.35)}px` }}>
                  {p.exchange.charAt(0)}
                </span>
              </div>
              {/* Tooltip — positioned dynamically to avoid clipping */}
              <div className={`absolute hidden group-hover:block z-30 pointer-events-none ${
                top < 40 ? 'top-full mt-1' : 'bottom-full mb-1'
              } ${left > 60 ? 'right-0' : left < 40 ? 'left-0' : 'left-1/2 -translate-x-1/2'}`}>
                <div className="bg-gray-900 text-white rounded-lg px-2.5 py-1.5 text-[9px] whitespace-nowrap shadow-xl border border-gray-700">
                  <div className="font-bold text-[10px] mb-0.5">{p.exchange}</div>
                  <div className="text-gray-300">{p.quadrant_label} &middot; {p.volume_fmt}</div>
                  <div className="text-gray-400">Net: {p.net_flow_fmt}</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend — compact exchange list */}
      <div className="flex flex-wrap gap-x-3 gap-y-1 mb-2">
        {behaviorMap.points.map((p) => {
          const qc = quadrantColors[p.quadrant] || quadrantColors.neutral;
          return (
            <div key={p.entity_id} className="flex items-center gap-1">
              <div className={`w-2 h-2 rounded-full ${qc.dot}`} />
              <span className="text-[9px] font-medium text-gray-500">{p.exchange}</span>
            </div>
          );
        })}
      </div>

      {/* Dominant venue */}
      {behaviorMap.dominant_venue && (
        <div className="pt-2 border-t border-gray-100" data-testid="cex-behavior-dominant">
          <div className="text-[9px] text-gray-400 uppercase tracking-wider mb-0.5">Dominant Venue</div>
          <div className="flex items-center justify-between">
            <span className="text-sm font-bold text-gray-900">{behaviorMap.dominant_venue.exchange}</span>
            <div className="text-right">
              <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                quadrantColors[behaviorMap.points[0]?.quadrant]?.bg || 'bg-gray-100'
              } ${quadrantColors[behaviorMap.points[0]?.quadrant]?.text || 'text-gray-600'}`}>
                {behaviorMap.dominant_venue.quadrant_label}
              </span>
              <span className="text-[9px] text-gray-400 ml-2">{behaviorMap.dominant_venue.share}%</span>
            </div>
          </div>
        </div>
      )}

      {/* Quadrant summary */}
      <div className="mt-2 grid grid-cols-2 gap-1.5">
        {(['accumulation', 'distribution', 'liquidity_hub', 'neutral'] as const).map(q => {
          const qd = behaviorMap.quadrant_summary[q];
          if (!qd || qd.count === 0) return null;
          const qc = quadrantColors[q];
          return (
            <div key={q} className="flex items-center gap-1.5">
              <div className={`w-2 h-2 rounded-full ${qc.dot}`} />
              <span className="text-[9px] text-gray-500">{qd.count} exchange{qd.count > 1 ? 's' : ''}</span>
            </div>
          );
        })}
      </div>
    </IntelligenceBlock>
  );
}


/* ══════════════════════════════════════════════════════════
   FLOW COMPOSITION (Sprint B)
   ══════════════════════════════════════════════════════════ */
function FlowCompositionBlock({ classification, loading, chainId }: { classification: FlowClassification | null; loading: boolean; chainId: number }) {
  const [expandedType, setExpandedType] = useState<string | null>(null);
  if (loading && !classification) return <Skeleton dark />;
  if (!classification) return null;

  const typeColors: Record<string, { bar: string; text: string }> = {
    distribution: { bar: 'bg-red-400', text: 'text-red-400' },
    accumulation: { bar: 'bg-emerald-400', text: 'text-emerald-400' },
    liquidity_provision: { bar: 'bg-blue-400', text: 'text-blue-400' },
    market_making: { bar: 'bg-amber-400', text: 'text-amber-400' },
  };

  return (
    <IntelligenceBlock dark testId="cex-flow-composition">
      <div className="flex items-center gap-2 mb-4">
        <Layers className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Flow Composition</h3>
      </div>

      {/* Dominant */}
      <div className="mb-4">
        <div className="text-[9px] text-gray-500 uppercase tracking-wider mb-1">Dominant Flow</div>
        <div className="text-lg font-black text-white" data-testid="cex-flow-dominant">
          {classification.dominant_label}
          <span className="text-sm text-gray-500 ml-2">{classification.dominant_pct}%</span>
        </div>
        <div className="text-[10px] text-gray-400 mt-0.5">{classification.interpretation}</div>
      </div>

      {/* Stacked bar */}
      <div className="h-4 bg-gray-800 rounded-full overflow-hidden flex mb-3">
        {classification.composition.map((c) => {
          const tc = typeColors[c.type] || typeColors.distribution;
          return c.percentage > 0 ? (
            <div key={c.type} className={`h-full ${tc.bar} transition-all duration-700`}
              style={{ width: `${c.percentage}%` }} title={`${c.label}: ${c.percentage}%`} />
          ) : null;
        })}
      </div>

      {/* Breakdown */}
      <div className="space-y-2">
        {classification.composition.map((c) => {
          const tc = typeColors[c.type] || typeColors.distribution;
          const hasTxs = c.top_transactions && c.top_transactions.length > 0;
          const isExpanded = expandedType === c.type;
          return (
            <div key={c.type} data-testid={`cex-flow-type-${c.type}`}>
              <div
                className={`flex items-center justify-between ${hasTxs ? 'cursor-pointer hover:bg-gray-800/50 -mx-2 px-2 py-1 rounded' : ''}`}
                onClick={() => hasTxs && setExpandedType(isExpanded ? null : c.type)}
              >
                <div className="flex items-center gap-2">
                  {hasTxs && (isExpanded ? <ChevronDown className="w-3 h-3 text-gray-500" /> : <ChevronRight className="w-3 h-3 text-gray-500" />)}
                  <div className={`w-2 h-2 rounded-full ${tc.bar}`} />
                  <span className="text-[11px] font-bold text-gray-300">{c.label}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-bold tabular-nums ${tc.text}`}>{c.percentage}%</span>
                  <span className="text-[9px] text-gray-500 tabular-nums">{c.usd_fmt}</span>
                </div>
              </div>
              {isExpanded && c.top_transactions && (
                <TxRefList txs={c.top_transactions} chainId={chainId} dark />
              )}
            </div>
          );
        })}
      </div>
    </IntelligenceBlock>
  );
}


/* ══════════════════════════════════════════════════════════
   Exchange Pressure (from Sprint A)
   ══════════════════════════════════════════════════════════ */
function ExchangePressureBlock({ pressure, loading, chainId }: { pressure: ExchangePressure | null; loading: boolean; chainId: number }) {
  const [showTxs, setShowTxs] = useState(false);
  if (loading && !pressure) return <Skeleton />;
  if (!pressure) return null;
  const total = pressure.deposits + pressure.withdrawals;
  const depPct = total > 0 ? (pressure.deposits / total) * 100 : 50;
  const hasTxs = (pressure.top_deposit_txs?.length || 0) > 0 || (pressure.top_withdrawal_txs?.length || 0) > 0;

  return (
    <IntelligenceBlock testId="cex-pressure">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em] mb-4">Exchange Pressure</h3>
      <div className="space-y-3">
        <div className="h-3 bg-gray-100 rounded-full overflow-hidden flex">
          <div className="h-full bg-red-400 transition-all" style={{ width: `${depPct}%` }} />
          <div className="h-full bg-emerald-400 transition-all" style={{ width: `${100 - depPct}%` }} />
        </div>
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-red-600 font-bold">Deposits {pressure.deposits_fmt}</span>
          <span className="text-emerald-600 font-bold">Withdrawals {pressure.withdrawals_fmt}</span>
        </div>
        <div className="grid grid-cols-2 gap-3 pt-2 border-t border-gray-100">
          <div>
            <div className="text-[9px] text-gray-400 uppercase tracking-wider">Active Exchanges</div>
            <div className="text-lg font-black text-gray-900">{pressure.active_exchanges}</div>
          </div>
          <div>
            <div className="text-[9px] text-gray-400 uppercase tracking-wider">Total Transfers</div>
            <div className="text-lg font-black text-gray-900">{pressure.total_transfers.toLocaleString()}</div>
          </div>
        </div>
        {hasTxs && (
          <div className="pt-2 border-t border-gray-100">
            <button onClick={() => setShowTxs(!showTxs)}
              className="text-[10px] text-violet-500 hover:text-violet-700 font-semibold flex items-center gap-0.5 transition-colors"
              data-testid="cex-pressure-expand-txs">
              {showTxs ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              Top Transactions
            </button>
            {showTxs && (
              <div className="mt-2 space-y-2">
                {pressure.top_deposit_txs && pressure.top_deposit_txs.length > 0 && (
                  <div>
                    <div className="text-[9px] text-red-500 font-bold uppercase mb-1">Top Deposits</div>
                    <TxRefList txs={pressure.top_deposit_txs} chainId={chainId} />
                  </div>
                )}
                {pressure.top_withdrawal_txs && pressure.top_withdrawal_txs.length > 0 && (
                  <div>
                    <div className="text-[9px] text-emerald-500 font-bold uppercase mb-1">Top Withdrawals</div>
                    <TxRefList txs={pressure.top_withdrawal_txs} chainId={chainId} />
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </IntelligenceBlock>
  );
}


/* ══════════════════════════════════════════════════════════
   Stablecoin Power
   ══════════════════════════════════════════════════════════ */
function StablecoinPowerBlock({ power, loading, chainId }: { power: StablecoinPower | null; loading: boolean; chainId: number }) {
  const [expandedStable, setExpandedStable] = useState<string | null>(null);
  if (loading && !power) return <Skeleton dark />;
  if (!power) return null;
  const stables = [
    { name: 'USDT', inflow: power.usdt_in, wallets: power.usdt_top_wallets || [] },
    { name: 'USDC', inflow: power.usdc_in, wallets: power.usdc_top_wallets || [] },
    { name: 'DAI', inflow: power.dai_in, wallets: power.dai_top_wallets || [] },
  ].filter(s => s.inflow > 0);
  const maxStable = Math.max(...stables.map(s => s.inflow), 1);
  const powerColor = power.bias === 'buying_power' ? 'text-emerald-400' : 'text-red-400';

  return (
    <IntelligenceBlock dark testId="cex-stablecoin">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em] mb-4">Stablecoin Power</h3>
      <div className="space-y-3">
        <div>
          <div className="text-[9px] text-gray-500 uppercase tracking-wider mb-0.5">Net Power</div>
          <div className={`text-2xl font-black tabular-nums ${powerColor}`} data-testid="cex-stable-power">
            {power.net_power >= 0 ? '+' : ''}{fmtUsd(power.net_power)}
          </div>
          <div className={`text-[10px] font-bold uppercase ${powerColor}`}>
            {power.bias === 'buying_power' ? 'Fresh buying power' : 'Capital leaving'}
          </div>
        </div>
        {stables.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-gray-800">
            {stables.map(s => {
              const hasWallets = s.wallets.length > 0;
              const isExpanded = expandedStable === s.name;
              return (
                <div key={s.name}>
                  <div
                    className={`flex items-center justify-between mb-0.5 ${hasWallets ? 'cursor-pointer hover:bg-gray-800/50 -mx-1 px-1 py-0.5 rounded' : ''}`}
                    onClick={() => hasWallets && setExpandedStable(isExpanded ? null : s.name)}
                  >
                    <div className="flex items-center gap-1">
                      {hasWallets && (isExpanded ? <ChevronDown className="w-3 h-3 text-gray-500" /> : <ChevronRight className="w-3 h-3 text-gray-500" />)}
                      <span className="text-[10px] font-bold text-gray-400">{s.name}</span>
                    </div>
                    <span className="text-[10px] font-bold text-emerald-400 tabular-nums">+{fmtUsd(s.inflow)}</span>
                  </div>
                  {!isExpanded && (
                    <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
                      <div className="h-full bg-emerald-400 rounded-full transition-all duration-700"
                        style={{ width: `${(s.inflow / maxStable) * 100}%` }} />
                    </div>
                  )}
                  {isExpanded && (
                    <div className="mt-1 space-y-0.5 pl-2 border-l-2 border-violet-500/20" data-testid={`stable-wallets-${s.name}`}>
                      {s.wallets.map((w, wi) => (
                        <div key={w.wallet} className="flex items-center gap-2 py-0.5 group/sw">
                          <span className="text-[9px] text-gray-600 tabular-nums w-3">{wi + 1}.</span>
                          <a href={addressUrl(w.wallet, chainId)} target="_blank" rel="noopener noreferrer"
                            className="text-[10px] text-violet-400 font-mono hover:underline">
                            {shortAddr(w.wallet)}
                          </a>
                          <span className="text-[9px] text-emerald-400 font-bold tabular-nums ml-auto">{w.usd_fmt}</span>
                          <a href={addressUrl(w.wallet, chainId)} target="_blank" rel="noopener noreferrer"
                            className="opacity-0 group-hover/sw:opacity-100 transition-opacity">
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
        )}
      </div>
    </IntelligenceBlock>
  );
}


/* ══════════════════════════════════════════════════════════
   Market Liquidity Map
   ══════════════════════════════════════════════════════════ */
function MarketLiquidityMapBlock({ liquidity, loading }: { liquidity: MarketLiquidity | null; loading: boolean }) {
  if (loading && !liquidity) return <Skeleton dark />;
  if (!liquidity) return null;
  const total = liquidity.buy_power + liquidity.sell_supply;
  const buyPct = total > 0 ? (liquidity.buy_power / total) * 100 : 50;
  const netColor = liquidity.bias === 'bullish' ? 'text-emerald-400' : 'text-red-400';
  const netBg = liquidity.bias === 'bullish' ? 'bg-emerald-500/10' : 'bg-red-500/10';

  return (
    <IntelligenceBlock dark testId="cex-liquidity-map">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em] mb-4">Market Liquidity</h3>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-emerald-400 uppercase">Buy Power</span>
          <span className="text-sm font-black text-emerald-400 tabular-nums" data-testid="cex-buy-power">{liquidity.buy_power_fmt}</span>
        </div>
        <div className="h-3 bg-gray-800 rounded-full overflow-hidden flex">
          <div className="h-full bg-emerald-500/60 transition-all duration-700 rounded-l-full" style={{ width: `${buyPct}%` }} />
          <div className="h-full bg-red-500/60 transition-all duration-700 rounded-r-full" style={{ width: `${100 - buyPct}%` }} />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-red-400 uppercase">Sell Supply</span>
          <span className="text-sm font-black text-red-400 tabular-nums" data-testid="cex-sell-supply">{liquidity.sell_supply_fmt}</span>
        </div>
        <div className={`rounded-lg p-3 ${netBg}`}>
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Net Liquidity</span>
            <span className={`text-xl font-black tabular-nums ${netColor}`} data-testid="cex-net-liquidity">{liquidity.net_liquidity_fmt}</span>
          </div>
          {liquidity.interpretation && (
            <p className="text-[10px] text-gray-400 mt-1.5 leading-relaxed" data-testid="cex-liquidity-interpretation">{liquidity.interpretation}</p>
          )}
        </div>
      </div>
    </IntelligenceBlock>
  );
}


/* ══════════════════════════════════════════════════════════
   Exchange Flows — Behavior Panel
   ══════════════════════════════════════════════════════════ */
function ExchangeFlowsBlock({ exchanges, loading, chainId }: { exchanges: ExchangeFlow[]; loading: boolean; chainId: number }) {
  if (loading && exchanges.length === 0) return <Skeleton />;
  const maxFlow = Math.max(...exchanges.map(e => Math.abs(e.net_usd)), 1);
  const behaviorColors: Record<string, string> = {
    'Distribution': 'bg-red-100 text-red-700', 'Accumulation': 'bg-emerald-100 text-emerald-700',
    'Inventory Rebalance': 'bg-blue-100 text-blue-700', 'Neutral': 'bg-gray-100 text-gray-600',
  };

  return (
    <IntelligenceBlock testId="cex-flows">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em] mb-3">Exchange Flows</h3>
      <div className="space-y-2.5">
        {exchanges.filter(e => e.tx_count > 0).slice(0, 6).map((ex, i) => {
          const isPos = ex.net_usd >= 0;
          const barW = Math.max(8, (Math.abs(ex.net_usd) / maxFlow) * 100);
          const bColor = behaviorColors[ex.behavior_label] || behaviorColors['Neutral'];
          return (
            <div key={ex.entityId} data-testid={`cex-exchange-${i}`}>
              <div className="flex items-center justify-between mb-0.5">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-bold text-gray-900">{ex.entityName}</span>
                  <span className="text-[8px] text-gray-400 tabular-nums">{ex.market_share}%</span>
                </div>
                <span className={`text-[8px] font-bold px-1 py-0.5 rounded ${bColor}`}>{ex.behavior_label}</span>
              </div>
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-[9px] text-gray-400">{ex.dominant_direction}</span>
                <span className={`text-[10px] font-black tabular-nums ${isPos ? 'text-red-600' : 'text-emerald-600'}`}>{ex.net_fmt}</span>
              </div>
              <div className="h-1 bg-gray-100 rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all duration-700 ${isPos ? 'bg-red-400' : 'bg-emerald-400'}`}
                  style={{ width: `${barW}%` }} />
              </div>
              {ex.wallet_addresses && ex.wallet_addresses.length > 0 && (
                <WalletList wallets={ex.wallet_addresses} chainId={chainId} />
              )}
              {ex.top_transactions && ex.top_transactions.length > 0 && (
                <TxRefList txs={ex.top_transactions} chainId={chainId} />
              )}
            </div>
          );
        })}
      </div>
    </IntelligenceBlock>
  );
}


/* ══════════════════════════════════════════════════════════
   Largest Transfers with Impact
   ══════════════════════════════════════════════════════════ */
function LargestTransfersBlock({ transfers, loading, chainId }: { transfers: LargestTransfer[]; loading: boolean; chainId: number }) {
  if (loading && transfers.length === 0) return <Skeleton dark />;
  const impactColors: Record<string, string> = {
    'BUY LIQUIDITY': 'text-emerald-400 bg-emerald-500/10', 'SELL PRESSURE': 'text-red-400 bg-red-500/10',
    'ACCUMULATION': 'text-blue-400 bg-blue-500/10', 'CAPITAL EXIT': 'text-amber-400 bg-amber-500/10',
  };

  return (
    <IntelligenceBlock dark testId="cex-transfers">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em] mb-3">Largest Transfers</h3>
      {transfers.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-4">No large transfers</p>
      ) : (
        <div className="space-y-1.5">
          {transfers.slice(0, 6).map((t, i) => {
            const isDep = t.direction === 'deposit';
            const impColor = impactColors[t.impact_label] || 'text-gray-400 bg-gray-500/10';
            return (
              <div key={i} className="py-1" data-testid={`cex-transfer-${i}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    {isDep ? <ArrowDownRight className="w-3 h-3 text-red-400" /> : <ArrowUpRight className="w-3 h-3 text-emerald-400" />}
                    <span className="text-xs font-bold text-white">{t.token}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-bold text-white tabular-nums">{t.usd_fmt}</span>
                    <ArrowRight className="w-2.5 h-2.5 text-gray-600" />
                    <span className="text-[9px] text-gray-400">{t.exchange}</span>
                  </div>
                </div>
                <div className="mt-0.5 ml-4 flex items-center gap-1.5 flex-wrap">
                  <span className={`text-[8px] font-bold px-1 py-0.5 rounded ${impColor}`}>{t.impact_label}</span>
                  {t.significance && (
                    <span className={`text-[8px] font-bold px-1 py-0.5 rounded ${
                      t.significance === 'HIGH' ? 'text-amber-300 bg-amber-500/15' :
                      t.significance === 'MEDIUM' ? 'text-gray-300 bg-gray-500/15' :
                      'text-gray-500 bg-gray-500/10'
                    }`} data-testid={`cex-transfer-sig-${i}`}>{t.significance}</span>
                  )}
                  {t.from_address && (
                    <a href={addressUrl(t.from_address, chainId)} target="_blank" rel="noopener noreferrer"
                      className="text-[9px] text-violet-400 font-mono hover:underline" data-testid={`transfer-from-${i}`}>
                      {shortAddr(t.from_address)}
                    </a>
                  )}
                  {t.from_address && t.to_address && <ArrowRight className="w-2 h-2 text-gray-600" />}
                  {t.to_address && (
                    <a href={addressUrl(t.to_address, chainId)} target="_blank" rel="noopener noreferrer"
                      className="text-[9px] text-violet-400 font-mono hover:underline" data-testid={`transfer-to-${i}`}>
                      {shortAddr(t.to_address)}
                    </a>
                  )}
                  {t.tx_hash && (
                    <a href={txUrl(t.tx_hash, chainId)} target="_blank" rel="noopener noreferrer"
                      className="text-[8px] text-gray-500 hover:text-blue-400 flex items-center gap-0.5"
                      data-testid={`transfer-tx-${i}`}>
                      <ExternalLink className="w-2.5 h-2.5" />tx
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </IntelligenceBlock>
  );
}


/* ══════════════════════════════════════════════════════════
   Pump / Dump Setup with Drivers
   ══════════════════════════════════════════════════════════ */
function PumpSetupBlock({ setups, loading, chainId }: { setups: PumpSetup[]; loading: boolean; chainId: number }) {
  if (loading && setups.length === 0) return <Skeleton dark />;
  return (
    <IntelligenceBlock dark testId="cex-pump-setup">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em] mb-3">Pump / Dump Setup</h3>
      {setups.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-4">No setups detected</p>
      ) : (
        <div className="space-y-3">
          {setups.slice(0, 4).map((s, i) => {
            const pumpCol = s.pump_probability >= 65 ? 'text-emerald-400' : s.pump_probability >= 50 ? 'text-amber-400' : 'text-gray-400';
            return (
              <div key={s.token} data-testid={`pump-setup-${i}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-white">{s.token}</span>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-black tabular-nums ${pumpCol}`}>{s.pump_probability}%</span>
                    <span className="text-[9px] text-gray-500">/</span>
                    <span className="text-xs font-black tabular-nums text-red-400">{s.dump_risk}%</span>
                  </div>
                </div>
                <div className="h-1 bg-gray-800 rounded-full overflow-hidden flex mb-1 relative">
                  <div className="h-full bg-emerald-400 transition-all" style={{ width: `${s.pump_probability}%` }} />
                  <div className="h-full bg-red-400 transition-all" style={{ width: `${s.dump_risk}%` }} />
                  {/* Confidence band markers */}
                  {s.confidence_band && (
                    <>
                      <div className="absolute top-0 bottom-0 w-px bg-white/40" style={{ left: `${s.confidence_band.low}%` }} />
                      <div className="absolute top-0 bottom-0 w-px bg-white/40" style={{ left: `${s.confidence_band.high}%` }} />
                    </>
                  )}
                </div>
                {/* Confidence band label */}
                {s.confidence_band && (
                  <div className="flex items-center justify-between mb-1.5" data-testid={`pump-confidence-${i}`}>
                    <span className="text-[8px] text-gray-500">Range: {s.confidence_band.low}%-{s.confidence_band.high}%</span>
                    <span className={`text-[8px] font-bold px-1 py-0.5 rounded ${
                      s.confidence_band.level === 'high' ? 'text-emerald-400 bg-emerald-500/10' :
                      s.confidence_band.level === 'moderate' ? 'text-amber-400 bg-amber-500/10' :
                      'text-gray-400 bg-gray-500/10'
                    }`}>{s.confidence_band.level.toUpperCase()}</span>
                  </div>
                )}
                {s.drivers.length > 0 && (
                  <div className="bg-gray-800/50 rounded px-2 py-1.5">
                    {s.drivers.slice(0, 3).map((d, di) => (
                      <div key={di} className="text-[9px] text-gray-400 flex items-center gap-1">
                        <ChevronRight className="w-2 h-2 text-gray-600" />{d}
                      </div>
                    ))}
                  </div>
                )}
                {s.top_transactions && s.top_transactions.length > 0 && (
                  <TxRefList txs={s.top_transactions} chainId={chainId} dark />
                )}
              </div>
            );
          })}
        </div>
      )}
    </IntelligenceBlock>
  );
}


/* ══════════════════════════════════════════════════════════
   Exchange Rotation with Fallback
   ══════════════════════════════════════════════════════════ */
function ExchangeRotationBlock({ rotations, fallback, loading }: {
  rotations: ExchangeRotation[]; fallback: RotationFallback[]; loading: boolean;
}) {
  return (
    <IntelligenceBlock testId="cex-rotation">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em] mb-4">Exchange Rotation</h3>
      {rotations.length > 0 ? (
        <div className="space-y-3">
          {rotations.map((r, i) => (
            <div key={i} className="flex items-center justify-between py-1" data-testid={`cex-rotation-${i}`}>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-gray-900">{r.from_exchange}</span>
                <ArrowRight className="w-3.5 h-3.5 text-gray-400" />
                <span className="text-sm font-bold text-gray-900">{r.to_exchange}</span>
              </div>
              <div className="text-right">
                <div className="text-xs font-black text-gray-900 tabular-nums">{r.total_fmt}</div>
                <div className="text-[10px] text-gray-400">{r.top_token} &middot; {r.count} tx</div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="py-3">
          <div className="flex items-center gap-2 mb-3">
            <Minus className="w-4 h-4 text-gray-300" />
            <span className="text-sm text-gray-400">No rotation detected in current window</span>
          </div>
          {fallback.length > 0 ? (
            <div className="border-t border-gray-100 pt-3">
              <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-2">Recent Rotation</div>
              {fallback.map((r, i) => (
                <div key={i} className="flex items-center justify-between py-1" data-testid={`cex-rotation-fallback-${i}`}>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-gray-700">{r.from_exchange}</span>
                    <ArrowRight className="w-3 h-3 text-gray-300" />
                    <span className="text-sm font-bold text-gray-700">{r.to_exchange}</span>
                  </div>
                  <div className="text-right">
                    <div className="text-xs font-bold text-gray-600 tabular-nums">{r.total_fmt} {r.top_token}</div>
                    <div className="text-[10px] text-gray-400">({r.time_ago} ago)</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[10px] text-gray-300">Exchange-to-exchange flows appear here when detected</p>
          )}
        </div>
      )}
    </IntelligenceBlock>
  );
}

export default CexFlowTab;
