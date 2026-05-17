import React, { useState } from 'react';
import { ArrowRight, Users, ChevronDown, ChevronRight, ExternalLink, Copy, Check } from 'lucide-react';
import { addressUrl } from '../../../utils/explorer';
import type { SmartActor } from '../types/smartMoney';

export function TopSmartActorsBlock({ actors, loading, onOpenEntity, onNavigateToWallet, chainId }: {
  actors: SmartActor[];
  loading: boolean;
  onOpenEntity: (id: string, name?: string) => void;
  onNavigateToWallet?: (address: string, src: string, params?: Record<string, string>) => void;
  chainId?: number;
}) {
  if (loading && actors.length === 0) {
    return (
      <div className="rounded-2xl bg-white p-6 text-center" data-testid="top-actors-block">
        <div className="animate-spin w-6 h-6 border-2 border-gray-900 border-t-transparent rounded-full mx-auto" />
        <p className="text-gray-400 mt-3 text-sm">Loading top actors...</p>
      </div>
    );
  }
  if (actors.length === 0) return null;

  return (
    <div className="rounded-2xl bg-white p-6" data-testid="top-actors-block">
      <div className="flex items-center gap-3 mb-5">
        <Users className="w-5 h-5 text-gray-700" />
        <h3 className="font-bold text-gray-900">Top Smart Actors</h3>
        <span className="text-xs text-gray-400">{actors.length} actors</span>
      </div>

      <div className="space-y-3">
        {actors.slice(0, 8).map((actor, i) => (
          <ActorRow key={actor.wallet} actor={actor} index={i}
            onOpenEntity={onOpenEntity} onNavigateToWallet={onNavigateToWallet} chainId={chainId} />
        ))}
      </div>
    </div>
  );
}

function ActorRow({ actor, index, onOpenEntity, onNavigateToWallet, chainId }: {
  actor: SmartActor;
  index: number;
  onOpenEntity: (id: string) => void;
  onNavigateToWallet?: (address: string, src: string, params?: Record<string, string>) => void;
  chainId?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const isPositive = actor.net_flow_usd >= 0;
  const hasWallets = actor.wallet_addresses && actor.wallet_addresses.length > 0;

  return (
    <div data-testid={`top-actor-${index + 1}`}>
      <div
        className="flex items-center gap-4 py-2 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => onNavigateToWallet ? onNavigateToWallet(actor.wallet, 'actor') : onOpenEntity(actor.wallet, actor.name)}
      >
        <span className="text-xs text-gray-400 w-5 text-right tabular-nums">{index + 1}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-gray-900 truncate">{actor.name?.replace(/_/g, ' ')}</span>
            {hasWallets && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onNavigateToWallet?.(actor.wallet_addresses![0], 'actor');
                }}
                className="text-[10px] text-violet-500 hover:text-violet-400 font-mono transition-colors"
                data-testid={`actor-first-wallet-${index}`}
              >
                {actor.wallet_addresses![0].slice(0, 8)}...{actor.wallet_addresses![0].slice(-4)}
              </button>
            )}
            {actor.tokens.length > 0 && (
              <span className="text-[10px] text-gray-400">{actor.tokens.join(', ')}</span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-0.5">
            <span className="text-[10px] text-gray-400">{actor.trades} trades</span>
            <span className="text-[10px] text-gray-400">{actor.last_activity}</span>
            {hasWallets && actor.wallet_addresses!.length > 1 && (
              <button
                onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
                className="text-[10px] text-violet-500 hover:text-violet-400 font-semibold flex items-center gap-0.5 transition-colors"
                data-testid={`actor-expand-${index}`}
              >
                {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                {actor.wallet_addresses!.length} wallets
              </button>
            )}
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs font-bold text-gray-900">Score {actor.smart_score}</div>
          <div className={`text-xs font-semibold tabular-nums ${isPositive ? 'text-emerald-600' : 'text-red-600'}`}>
            {isPositive ? '+' : ''}{actor.net_flow_fmt}
          </div>
        </div>
        <ArrowRight className="w-3.5 h-3.5 text-gray-300 flex-shrink-0" />
      </div>

      {expanded && hasWallets && (
        <div className="ml-10 mt-1 space-y-0.5 pl-3 border-l-2 border-violet-500/20 mb-2">
          {actor.wallet_addresses!.map((addr, i) => (
            <div key={addr} className="flex items-center gap-2 group/w py-0.5" data-testid={`actor-wallet-${index}-${i}`}>
              <span className="text-[9px] text-gray-500 tabular-nums w-4">{i + 1}.</span>
              <button
                onClick={() => onNavigateToWallet?.(addr, 'actor')}
                className="text-[10px] text-violet-400 hover:text-violet-300 font-mono transition-colors"
              >
                {addr.slice(0, 8)}...{addr.slice(-6)}
              </button>
              {chainId && (
                <a href={addressUrl(addr, chainId)} target="_blank" rel="noopener noreferrer"
                  className="no-underline opacity-0 group-hover/w:opacity-100 transition-opacity">
                  <ExternalLink className="w-3 h-3 text-gray-500 hover:text-blue-400" />
                </a>
              )}
              <button
                onClick={() => {
                  navigator.clipboard.writeText(addr);
                  setCopiedIdx(i);
                  setTimeout(() => setCopiedIdx(null), 1500);
                }}
                className="opacity-0 group-hover/w:opacity-100 transition-opacity"
              >
                {copiedIdx === i
                  ? <Check className="w-3 h-3 text-emerald-400" />
                  : <Copy className="w-3 h-3 text-gray-500 hover:text-gray-300" />}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
