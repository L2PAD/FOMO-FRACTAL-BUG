/**
 * Smart Money — Main Page (Slim Orchestrator)
 * =============================================
 * Above-the-fold components loaded statically.
 * Heavy below-fold components loaded via React.lazy.
 */

import React, { useState, useCallback, useMemo, Suspense } from 'react';
import { RefreshCw, AlertCircle, Wallet } from 'lucide-react';
import { TooltipProvider } from '../../../components/ui/tooltip';
import { EntityDrawer } from '../components/EntityDrawer';
import { useOnchainChain } from '../context/OnchainChainContext';
import { explorerName } from '../utils/explorer';
import { useSmartMoneyContext } from './actors/hooks/useSmartMoneyContext';
import type { WindowKey } from './actors/types/smartMoney';

/* ── Above-the-fold (static imports) ─────────────────────── */
import {
  Hint,
  SmartMoneyNarrativeBlock,
  AlphaFeedBlock,
  ConvictionLeaderboard,
  SmartMoneyIndexCard,
  MarketPressureBlock,
  SmartMoneyList,
  SourceTraceability,
} from './actors/components';

/* ── Below-the-fold (lazy imports) ───────────────────────── */
const SmartMoneyBrainBlock = React.lazy(() =>
  import('./actors/components/SmartMoneyBrain').then(m => ({ default: m.SmartMoneyBrainBlock }))
);
const CapitalMovementBlock = React.lazy(() =>
  import('./actors/components/SmartMoneyRoutes').then(m => ({ default: m.CapitalMovementBlock }))
);
const SmartMoneyRadarBlock = React.lazy(() =>
  import('./actors/components/SmartMoneyEvents').then(m => ({ default: m.SmartMoneyRadarBlock }))
);
const SmartMoneyPatternsBlock = React.lazy(() =>
  import('./actors/components/SmartMoneyPhases').then(m => ({ default: m.SmartMoneyPatternsBlock }))
);
const SmartMoneyMapBlock = React.lazy(() =>
  import('./actors/components/SmartMoneyRoutes').then(m => ({ default: m.SmartMoneyMapBlock }))
);
const PlaybooksBlock = React.lazy(() =>
  import('./actors/components/SmartMoneyPlaybooks').then(m => ({ default: m.PlaybooksBlock }))
);
const TopSmartActorsBlock = React.lazy(() =>
  import('./actors/components/TopSmartActors').then(m => ({ default: m.TopSmartActorsBlock }))
);

const LazyFallback = () => (
  <div className="rounded-2xl bg-gray-50 p-8 text-center animate-pulse">
    <div className="w-6 h-6 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin mx-auto" />
  </div>
);

export function ActorsTab({ onOpenWallet }: { externalEntity?: string | null; onEntityConsumed?: () => void; onOpenWallet?: (addr: string) => void }) {
  const { chainId } = useOnchainChain();
  const ctx = useSmartMoneyContext(chainId);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);
  const [selectedEntityName, setSelectedEntityName] = useState<string | null>(null);

  const openEntity = (id: string, name?: string) => { setSelectedEntity(id); setSelectedEntityName(name || null); setDrawerOpen(true); };

  // Build a wallet address lookup map from context data (actors + signals)
  // Falls back to deterministic mock addresses when backend doesn't provide them
  const walletLookup = useMemo(() => {
    const map: Record<string, string[]> = {};
    for (const actor of ctx.actorsData) {
      if (actor.wallet && actor.wallet_addresses?.length) {
        map[actor.wallet] = actor.wallet_addresses;
        if (actor.name) map[actor.name] = actor.wallet_addresses;
      }
    }
    for (const sig of ctx.allSignals) {
      if (sig.wallet_addresses?.length) {
        map[sig.token] = sig.wallet_addresses;
      }
    }
    // Mock fallback: generate deterministic wallet addresses for entities without them
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
    const allEntities = [...ctx.buyers, ...ctx.sellers];
    for (const item of allEntities) {
      const key = item.entityId || item.entityName || '';
      if (key && !map[key]) {
        const count = 2 + Math.abs((key.charCodeAt(0) || 3) % 4);
        map[key] = mockAddr(key, count);
      }
    }
    return map;
  }, [ctx.actorsData, ctx.allSignals, ctx.buyers, ctx.sellers]);

  // P1: Navigation Context Layer — navigate to wallet page with context
  // Only navigates to /wallet/ for real addresses (0x...). Aliases open the drawer.
  const navigateToWallet = useCallback((address: string, src: string, params?: Record<string, string>) => {
    if (/^0x[a-fA-F0-9]{8,}$/i.test(address)) {
      if (onOpenWallet) {
        onOpenWallet(address);
      } else {
        const sp = new URLSearchParams({ src, ...params });
        globalThis.window.location.href = `/wallet/${encodeURIComponent(address)}?${sp.toString()}`;
      }
    } else {
      // Для не-адресов (entity aliases типа "okx") тоже открываем кошелёк
      if (onOpenWallet) {
        onOpenWallet(address);
      } else {
        setSelectedEntity(address);
        setDrawerOpen(true);
      }
    }
  }, [onOpenWallet]);

  return (
    <TooltipProvider>
      <div className="space-y-6" data-testid="smart-money-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900" data-testid="smart-money-title">
              <Hint text="Smart money = wallets with high win rate, large volume, or institutional activity. Tracked via on-chain flow analysis.">
                Smart Money
              </Hint>
            </h2>
            <p className="text-sm text-gray-500 mt-1">Track where large capital is moving</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[10px] text-gray-400 hidden lg:block">Source: {explorerName(chainId)} RPC</span>
            <div className="flex gap-1 p-1" data-testid="time-window-selector">
              {(['24h', '7d', '30d'] as WindowKey[]).map((w) => (
                <button key={w} onClick={() => ctx.setTimeWindow(w)}
                  className={`px-4 py-2 text-sm font-semibold transition-all ${ctx.timeWindow === w ? 'text-gray-900' : 'text-gray-400 hover:text-gray-700'}`}
                  data-testid={`window-${w}`}>{w.toUpperCase()}</button>
              ))}
            </div>
            <button onClick={ctx.refresh} disabled={ctx.loading || ctx.contextLoading}
              className="p-2.5 text-gray-600 hover:text-gray-900 transition-colors disabled:opacity-50"
              data-testid="refresh-btn">
              <RefreshCw className={`w-4 h-4 ${ctx.loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {ctx.error && (
          <div className="flex items-center gap-3 px-4 py-3 text-red-700 text-sm" data-testid="error-banner">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />{ctx.error}
          </div>
        )}

        {ctx.loading && !ctx.accData && (
          <div className="text-center py-16">
            <div className="animate-spin w-8 h-8 border-2 border-gray-900 border-t-transparent rounded-full mx-auto" />
            <p className="text-gray-500 mt-4 text-sm">Loading smart money data...</p>
          </div>
        )}

        {(!ctx.loading || ctx.accData) && (
          <>
            <SmartMoneyNarrativeBlock data={ctx.narrativeData} loading={ctx.narrativeLoading} />

            <AlphaFeedBlock signals={ctx.feedData} loading={ctx.contextLoading}
              filter={ctx.feedFilter} onFilterChange={ctx.setFeedFilter}
              tier={ctx.convictionTier} onTierChange={ctx.setConvictionTier}
              onRefresh={ctx.loadContext} onNavigateToWallet={navigateToWallet} />

            <ConvictionLeaderboard signals={ctx.allSignals} loading={ctx.contextLoading} onNavigateToWallet={navigateToWallet} chainId={chainId} />

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
              <div className="lg:col-span-3">
                <MarketPressureBlock totalBuy={ctx.totalBuy} totalSell={ctx.totalSell}
                  netFlow={ctx.netFlow} isBullish={ctx.isBullish} timeWindow={ctx.timeWindow} />
              </div>
              <SmartMoneyIndexCard score={ctx.smi.score} confidence={ctx.smi.confidence} />
            </div>

            <Suspense fallback={<LazyFallback />}>
              <SmartMoneyBrainBlock signals={ctx.brainData} loading={ctx.brainLoading} chainId={chainId} onNavigateToWallet={navigateToWallet} />
            </Suspense>

            {ctx.capitalFlows.length > 0 && (
              <Suspense fallback={<LazyFallback />}>
                <CapitalMovementBlock flows={ctx.capitalFlows} onEntityClick={openEntity} chainId={chainId} />
              </Suspense>
            )}

            <Suspense fallback={<LazyFallback />}>
              <SmartMoneyRadarBlock events={ctx.sortedRadarData} loading={ctx.radarLoading}
                sortBy={ctx.radarSort} onSortChange={ctx.setRadarSort}
                onRefresh={ctx.loadContext}
                onOpenWallet={(addr: string) => navigateToWallet(addr, 'event')}
                onOpenEntity={openEntity} chainId={chainId} />
            </Suspense>

            <Suspense fallback={<LazyFallback />}>
              <SmartMoneyPatternsBlock patterns={ctx.patternsData} loading={ctx.patternsLoading}
                onOpenWallet={(addr: string) => navigateToWallet(addr, 'pattern')} chainId={chainId} />
            </Suspense>
            <Suspense fallback={<LazyFallback />}>
              <SmartMoneyMapBlock data={ctx.mapData} loading={ctx.mapLoading}
                onOpenWallet={(addr: string) => navigateToWallet(addr, 'route')} />
            </Suspense>
            <Suspense fallback={<LazyFallback />}>
              <PlaybooksBlock playbooks={ctx.playbooksData} loading={ctx.contextLoading} onNavigateToWallet={navigateToWallet} chainId={chainId} />
            </Suspense>
            <Suspense fallback={<LazyFallback />}>
              <TopSmartActorsBlock actors={ctx.actorsData} loading={ctx.contextLoading}
                onOpenEntity={openEntity} onNavigateToWallet={navigateToWallet} chainId={chainId} />
            </Suspense>

            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-gray-500">Sort by</span>
                <div className="flex gap-1 p-0.5" data-testid="sort-controls">
                  {([['flow', 'Net Flow'], ['volume', 'Volume'], ['trades', 'Trades']] as const).map(([key, label]) => (
                    <button key={key} onClick={() => ctx.setSortBy(key)}
                      className={`px-3 py-1.5 text-xs font-semibold transition-all ${ctx.sortBy === key ? 'text-gray-900' : 'text-gray-400 hover:text-gray-700'}`}
                      data-testid={`sort-${key}`}>{label}</button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <SmartMoneyList title="Smart Money Buying" items={ctx.buyers.slice(0, 10)} positive onEntityClick={openEntity} chainId={chainId} walletLookup={walletLookup} />
                <SmartMoneyList title="Smart Money Selling" items={ctx.sellers.slice(0, 10)} positive={false} onEntityClick={openEntity} chainId={chainId} walletLookup={walletLookup} />
              </div>
            </div>

            <SourceTraceability chainId={chainId} lastUpdate={ctx.lastUpdate} />

            {ctx.buyers.length === 0 && ctx.sellers.length === 0 && (
              <div className="text-center py-16" data-testid="no-data">
                <Wallet className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                <h3 className="text-lg font-semibold text-gray-600">No Smart Money Data</h3>
                <p className="text-gray-400 text-sm mt-1">Flow data not yet available for this window</p>
              </div>
            )}
          </>
        )}

        <EntityDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)}
          entityId={selectedEntity} window={ctx.timeWindow} chainId={chainId}
          walletAddresses={selectedEntity ? (walletLookup[selectedEntity] || []) : []}
          fallbackTitle={selectedEntityName || undefined}
          onOpenSignals={(id: string) => { globalThis.window.location.href = `/intelligence/onchain-v3?tab=signals&entity=${id}`; }}
          onOpenAssets={(token: string) => { globalThis.window.location.href = `/intelligence/onchain-v3?tab=assets&token=${token}`; }}
          onOpenWallet={(addr: string) => { onOpenWallet?.(addr); }} />
      </div>
    </TooltipProvider>
  );
}

export default ActorsTab;
