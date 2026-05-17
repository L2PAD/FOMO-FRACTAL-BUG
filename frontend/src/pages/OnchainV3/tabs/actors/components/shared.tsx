import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, ExternalLink, Copy, Check } from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from '../../../../../components/ui/tooltip';
import { explorerName, addressUrl } from '../../../utils/explorer';
import { timeSince } from '../helpers';

/** Reusable expandable wallet list. Used across all Smart Money blocks. */
export function WalletExpandSection({ wallets, chainId, onOpenWallet, label }: {
  wallets: string[];
  chainId?: number;
  onOpenWallet?: (addr: string) => void;
  label?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  if (!wallets?.length) return null;

  return (
    <div className="mt-2" data-testid="wallet-expand-section">
      <button
        onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
        className="text-[11px] text-violet-500 hover:text-violet-300 font-semibold transition-colors flex items-center gap-1"
        data-testid="wallet-expand-btn"
      >
        {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        {label || `${wallets.length} wallets`}
      </button>
      {expanded && (
        <div className="mt-1.5 space-y-1 pl-3 border-l-2 border-violet-500/20">
          {wallets.map((addr, i) => (
            <div key={addr} className="flex items-center gap-2 group/w py-0.5" data-testid={`expand-wallet-${i}`}>
              <span className="text-[9px] text-gray-500 tabular-nums w-4">{i + 1}.</span>
              <button
                onClick={(e) => { e.stopPropagation(); onOpenWallet?.(addr); }}
                className="text-[10px] text-violet-400 hover:text-violet-300 font-mono transition-colors truncate"
                data-testid={`expand-wallet-link-${i}`}
              >
                {addr.slice(0, 8)}...{addr.slice(-6)}
              </button>
              {chainId && (
                <a
                  href={addressUrl(addr, chainId)}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="opacity-0 group-hover/w:opacity-100 transition-opacity"
                >
                  <ExternalLink className="w-3 h-3 text-gray-500 hover:text-blue-400" />
                </a>
              )}
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
  );
}

export function Hint({ children, text }: { children: React.ReactNode; text: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild><span className="cursor-help">{children}</span></TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs text-xs">{text}</TooltipContent>
    </Tooltip>
  );
}

export function SourceTraceability({ chainId, lastUpdate }: { chainId: number; lastUpdate: Date | null }) {
  const [ago, setAgo] = useState('---');

  useEffect(() => {
    if (!lastUpdate) return;
    const tick = () => setAgo(timeSince(lastUpdate));
    tick();
    const id = setInterval(tick, 5000);
    return () => clearInterval(id);
  }, [lastUpdate]);

  return (
    <div className="flex items-center justify-between px-4 py-3 text-xs text-gray-400" data-testid="source-traceability">
      <Tooltip delayDuration={200}>
        <TooltipTrigger asChild>
          <div className="flex items-center gap-4 cursor-default">
            <span>DEX swap events</span>
            <span>{explorerName(chainId)} RPC</span>
          </div>
        </TooltipTrigger>
        <TooltipContent className="text-xs max-w-[260px]">
          Smart money flows are calculated from detected DEX transactions and on-chain transfer events via {explorerName(chainId)} RPC.
        </TooltipContent>
      </Tooltip>
      <span data-testid="last-update">Last update: {ago}</span>
    </div>
  );
}
