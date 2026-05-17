import React from 'react';
import { ArrowRight, ExternalLink } from 'lucide-react';
import { IntelligenceBlock } from '../../../../../components/intelligence';
import type { SmartActor } from '../hooks/useTokenIntelligence';

const shortAddr = (a: string) => a ? `${a.slice(0, 6)}...${a.slice(-4)}` : '';

const STRATEGY_LABELS: Record<string, string> = {
  'dex': 'DEX Trader',
  'market': 'Market Maker',
  'exchange': 'Exchange',
  'whale': 'Whale',
  'fund': 'Fund',
  'protocol': 'Protocol',
  'unknown': 'Unknown',
};

function inferStrategy(actor: SmartActor): string {
  const name = actor.name.toLowerCase();
  if (name.includes('okx') || name.includes('binance') || name.includes('coinbase') || name.includes('exchange') || name.includes('hot_wallet')) return 'Exchange';
  if (name.includes('dex') || name.includes('uniswap') || name.includes('sushi')) return 'DEX Trader';
  if (name.includes('market') || name.includes('maker')) return 'Market Maker';
  if (name.includes('whale')) return 'Whale';
  if (name.includes('fund') || name.includes('capital')) return 'Fund';
  if (actor.trades > 50) return 'Active Trader';
  if (Math.abs(actor.net_flow_usd) > 1e6) return 'Whale';
  return 'Rotation Trader';
}

export function WalletActivity({ actors, loading, onOpenWallet }: {
  actors: SmartActor[];
  loading: boolean;
  onOpenWallet?: (addr: string) => void;
}) {
  if (loading && actors.length === 0) {
    return (
      <IntelligenceBlock testId="wallet-activity">
        <div className="py-8 text-center">
          <div className="animate-spin w-5 h-5 border-2 border-gray-400 border-t-transparent rounded-full mx-auto" />
        </div>
      </IntelligenceBlock>
    );
  }

  return (
    <IntelligenceBlock testId="wallet-activity">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Top Wallet Activity</h3>
      {actors.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">No wallet data</p>
      ) : (
        <div className="space-y-2">
          {actors.slice(0, 5).map((a, i) => {
            const isPos = a.net_flow_usd >= 0;
            const strategy = inferStrategy(a);
            return (
              <div
                key={a.wallet}
                onClick={() => onOpenWallet?.(a.wallet)}
                className={`flex items-center gap-3 py-2 ${onOpenWallet ? 'cursor-pointer hover:bg-gray-50' : ''} transition-colors`}
                data-testid={`wallet-actor-${i}`}
              >
                <span className="text-xs text-gray-400 w-4 text-right tabular-nums">{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-gray-900 truncate">{a.name}</span>
                    <span className="text-[9px] font-bold text-gray-400 uppercase">{strategy}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    {a.wallet && a.wallet.startsWith('0x') && (
                      <a href={`https://etherscan.io/address/${a.wallet}`} target="_blank" rel="noopener noreferrer"
                        className="no-underline text-[10px] text-violet-500 hover:text-violet-700 font-mono transition-colors flex items-center gap-0.5"
                        data-testid={`wallet-addr-link-${i}`}
                        onClick={(e) => e.stopPropagation()}>
                        {shortAddr(a.wallet)} <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    )}
                    {(a as any).wallet_addresses?.filter((w: string) => w !== a.wallet).slice(0, 2).map((w: string, wi: number) => (
                      <a key={wi} href={`https://etherscan.io/address/${w}`} target="_blank" rel="noopener noreferrer"
                        className="no-underline text-[10px] text-gray-400 hover:text-violet-400 font-mono transition-colors flex items-center gap-0.5"
                        data-testid={`wallet-extra-link-${i}-${wi}`}
                        onClick={(e) => e.stopPropagation()}>
                        {shortAddr(w)} <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    ))}
                    <span className="text-[10px] text-gray-400">Score {a.smart_score}</span>
                    <span className="text-[10px] text-gray-400">{a.trades} trades</span>
                    <span className="text-[10px] text-gray-400">{a.last_activity}</span>
                  </div>
                </div>
                <span className={`text-xs font-bold tabular-nums ${isPos ? 'text-emerald-600' : 'text-red-600'}`}>
                  {a.net_flow_fmt}
                </span>
                {onOpenWallet && <ArrowRight className="w-3 h-3 text-gray-300" />}
              </div>
            );
          })}
        </div>
      )}
    </IntelligenceBlock>
  );
}
