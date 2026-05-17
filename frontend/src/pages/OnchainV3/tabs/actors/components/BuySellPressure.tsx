import React, { useState } from 'react';
import { TrendingUp, TrendingDown, ExternalLink, Copy, Eye, ChevronDown, ChevronRight, Check } from 'lucide-react';
import {
  fmtUsdSigned, shortAddr, isAddress, displayName, typeLabel,
  getEntityColor, getEntityIcon, activityScore, copyToClipboard,
} from '../helpers';
import { addressUrl, explorerName } from '../../../utils/explorer';
import type { ActorItem } from '../types/smartMoney';

export function SmartMoneyList({ title, items, positive, onEntityClick, chainId, walletLookup }: {
  title: string;
  items: ActorItem[];
  positive: boolean;
  onEntityClick: (id: string, name?: string) => void;
  chainId: number;
  walletLookup?: Record<string, string[]>;
}) {
  return (
    <div className="rounded-2xl bg-white overflow-hidden" data-testid={positive ? 'buying-block' : 'selling-block'}>
      <div className="flex items-center gap-3 px-5 py-4">
        <div className={`w-8 h-8 flex items-center justify-center ${positive ? 'text-emerald-600' : 'text-red-600'}`}>
          {positive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
        </div>
        <h3 className="font-bold text-gray-900">{title}</h3>
        <span className="ml-auto text-xs text-gray-400">{items.length} entities</span>
      </div>

      <div className="max-h-[500px] overflow-y-auto">
        {items.map((item, i) => (
          <BuySellRow
            key={item.entityId}
            item={item}
            index={i}
            positive={positive}
            onEntityClick={onEntityClick}
            chainId={chainId}
            walletAddresses={walletLookup?.[item.entityId] || walletLookup?.[item.entityName || ''] || []}
          />
        ))}
        {items.length === 0 && (
          <div className="text-center py-10 text-gray-400 text-sm">No data</div>
        )}
      </div>
    </div>
  );
}

function BuySellRow({ item, index, positive, onEntityClick, chainId, walletAddresses }: {
  item: ActorItem;
  index: number;
  positive: boolean;
  onEntityClick: (id: string, name?: string) => void;
  chainId: number;
  walletAddresses: string[];
}) {
  const [expanded, setExpanded] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const color = getEntityColor(item.entityType);
  const name = displayName(item);
  const hasAddr = isAddress(item.entityId);
  const score = activityScore(item);
  const hasWallets = walletAddresses.length > 0;

  return (
    <div className="px-5 py-3.5 hover:bg-gray-50 transition-colors group"
      data-testid={`${positive ? 'buyer' : 'seller'}-row-${index + 1}`}>
      <div className="flex items-center gap-4 cursor-pointer" onClick={() => onEntityClick(item.entityId, name)}>
        <div className="w-6 text-center text-xs font-bold text-gray-400">{index + 1}</div>
        <div className={`w-9 h-9 flex items-center justify-center ${color.text}`}>
          {getEntityIcon(item.entityType)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-gray-900 truncate text-sm">{name}</span>
            <span className={`text-[10px] font-bold ${color.text}`}>{typeLabel(item.entityType)}</span>
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            {hasAddr && (
              <button onClick={(e) => { e.stopPropagation(); onEntityClick(item.entityId, name); }}
                className="text-[11px] text-violet-500 hover:text-violet-400 font-mono transition-colors"
                data-testid={`buysell-wallet-${item.entityId.slice(0, 8)}`}>
                {shortAddr(item.entityId)}
              </button>
            )}
            <span className="text-[11px] text-gray-400">{item.trades.toLocaleString()} trades</span>
            <span className={`text-[10px] font-semibold ${score.color}`}>{score.label}</span>
          </div>
          {hasAddr && (
            <div className="flex items-center gap-2 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <a href={addressUrl(item.entityId, chainId)} target="_blank" rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="text-[10px] text-blue-500 hover:text-blue-700 flex items-center gap-0.5">
                <ExternalLink className="w-3 h-3" />{explorerName(chainId)}
              </a>
              <button onClick={(e) => { e.stopPropagation(); copyToClipboard(item.entityId); }}
                className="text-[10px] text-gray-400 hover:text-gray-600 flex items-center gap-0.5">
                <Copy className="w-3 h-3" />copy
              </button>
            </div>
          )}
        </div>
        <div className="text-right">
          <div className={`text-lg font-bold ${positive ? 'text-emerald-600' : 'text-red-600'}`}>
            {fmtUsdSigned(item.netUsd)}
          </div>
        </div>
        <Eye className="w-4 h-4 text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
      </div>

      {hasWallets && (
        <div className="ml-16 mt-1">
          <button
            onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
            className="text-[10px] text-violet-500 hover:text-violet-400 font-semibold flex items-center gap-0.5 transition-colors"
            data-testid={`buysell-expand-${index}`}
          >
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            {walletAddresses.length} wallets
          </button>
          {expanded && (
            <div className="mt-1 space-y-0.5 pl-3 border-l-2 border-violet-500/20">
              {walletAddresses.map((addr, i) => (
                <div key={addr} className="flex items-center gap-2 group/w py-0.5" data-testid={`buysell-wallet-${index}-${i}`}>
                  <span className="text-[9px] text-gray-500 tabular-nums w-4">{i + 1}.</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); onEntityClick(addr); }}
                    className="text-[10px] text-violet-400 hover:text-violet-300 font-mono transition-colors"
                  >
                    {addr.slice(0, 8)}...{addr.slice(-6)}
                  </button>
                  <a href={addressUrl(addr, chainId)} target="_blank" rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="opacity-0 group-hover/w:opacity-100 transition-opacity">
                    <ExternalLink className="w-3 h-3 text-gray-500 hover:text-blue-400" />
                  </a>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
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
      )}
    </div>
  );
}
