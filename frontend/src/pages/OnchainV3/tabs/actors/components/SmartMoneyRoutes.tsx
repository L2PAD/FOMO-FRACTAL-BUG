import React, { useState } from 'react';
import { ArrowRight, ExternalLink, ChevronDown, ChevronRight, Copy, Check } from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from '../../../../../components/ui/tooltip';
import { fmtUsd, getEntityColor, getEntityIcon, typeLabel, shortAddr } from '../helpers';
import { addressUrl } from '../../../utils/explorer';
import type { MapData } from '../types/smartMoney';

const routeTypeConfig: Record<string, { color: string; bg: string; label: string }> = {
  accumulation: { color: 'text-emerald-600', bg: '', label: 'Accumulation' },
  distribution: { color: 'text-red-600', bg: '', label: 'Distribution' },
  rotation: { color: 'text-blue-600', bg: '', label: 'Rotation' },
  exit: { color: 'text-amber-600', bg: '', label: 'Exit' },
};

export function SmartMoneyMapBlock({ data, loading, onOpenWallet }: { data: MapData | null; loading: boolean; onOpenWallet?: (addr: string) => void }) {
  if (loading && !data) {
    return (
      <div className="rounded-2xl bg-white p-6 text-center" data-testid="map-block">
        <div className="animate-spin w-6 h-6 border-2 border-gray-900 border-t-transparent rounded-full mx-auto" />
        <p className="text-gray-400 mt-3 text-sm">Building capital flow map...</p>
      </div>
    );
  }
  if (!data || data.routes.length === 0) return null;

  const { routes, destination_heat, source_heat, flow_summary } = data;

  return (
    <div className="rounded-2xl bg-white overflow-hidden" data-testid="map-block">
      <div className="px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 flex items-center justify-center">
            <ArrowRight className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <h3 className="font-bold text-gray-900">Smart Money Capital Routes</h3>
            <p className="text-xs text-gray-400">Capital flow routes</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {Object.entries(flow_summary).filter(([,v]) => v > 0).map(([type, count]) => {
            const cfg = routeTypeConfig[type] || routeTypeConfig.accumulation;
            return (
              <span key={type} className={`text-[10px] font-bold ${cfg.color}`}
                data-testid={`map-summary-${type}`}>
                {cfg.label} {count}
              </span>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-0">
        <div className="lg:col-span-2 bg-white">
          <div className="px-5 py-3">
            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-3">Capital Routes</div>
            <div className="space-y-2.5">
              {routes.slice(0, 8).map((r, i) => {
                const cfg = routeTypeConfig[r.route_type] || routeTypeConfig.accumulation;
                const isRotation = r.route_type === 'rotation';
                return (
                  <div key={i} className="flex items-center gap-3 py-2 group hover:bg-gray-50 rounded-lg px-2 -mx-2 transition-colors"
                    data-testid={`map-route-${i + 1}`}>
                    <span className={`text-[9px] font-bold ${cfg.color} flex-shrink-0`}>
                      {cfg.label}
                    </span>
                    <div className="flex items-center gap-1.5 text-sm text-gray-700 min-w-0 flex-1">
                      <span className="font-semibold truncate max-w-[140px]">{r.source_entity}</span>
                      {r.source_wallet && (
                        <button onClick={() => onOpenWallet?.(r.source_wallet)}
                          className="text-[9px] text-violet-500 hover:text-violet-400 font-mono transition-colors flex-shrink-0"
                          data-testid={`route-wallet-${i}`}>
                          {shortAddr(r.source_wallet)}
                        </button>
                      )}
                      <ArrowRight className="w-3 h-3 text-gray-300 flex-shrink-0" />
                      <span className="text-gray-400 text-xs">{r.protocol}</span>
                      <ArrowRight className="w-3 h-3 text-gray-300 flex-shrink-0" />
                      {isRotation ? (
                        <span className="font-bold">
                          <span className="text-red-500">{r.from_token}</span>
                          <span className="text-gray-400 mx-1">-&gt;</span>
                          <span className="text-emerald-500">{r.to_token}</span>
                        </span>
                      ) : (
                        <span className="font-bold text-gray-900">{r.token}</span>
                      )}
                    </div>
                    <div className="text-right flex-shrink-0 flex items-center gap-3">
                      <span className="text-sm font-bold text-gray-700">{fmtUsd(r.volume_usd)}</span>
                      <span className="text-[10px] text-gray-400">imp {r.impact_score}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="bg-white">
          <div className="px-5 py-3">
            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-3">Top Destinations</div>
            <div className="space-y-2">
              {destination_heat.slice(0, 6).map((d, i) => {
                const isPos = d.net_flow_usd > 0;
                const maxFlow = Math.max(...destination_heat.map(h => Math.abs(h.net_flow_usd)));
                const barWidth = Math.max(5, (Math.abs(d.net_flow_usd) / maxFlow) * 100);
                return (
                  <div key={d.token} className="group" data-testid={`map-dest-${d.token}`}>
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-sm font-bold text-gray-900">{d.token}</span>
                      <span className={`text-sm font-bold ${isPos ? 'text-emerald-600' : 'text-red-600'}`}>
                        {isPos ? '+' : ''}{fmtUsd(d.net_flow_usd)}
                      </span>
                    </div>
                    <div className="h-1 bg-gray-100 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${isPos ? 'bg-emerald-400' : 'bg-red-400'}`}
                        style={{ width: `${barWidth}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-3 mt-5">Top Sources</div>
            <div className="space-y-1.5">
              {source_heat.slice(0, 5).map((s, i) => (
                <div key={i} className="flex items-center justify-between" data-testid={`map-source-${i + 1}`}>
                  <span className="text-xs text-gray-700 truncate max-w-[150px]">{s.name}</span>
                  <span className="text-xs font-bold text-gray-500">{fmtUsd(s.total_flow_usd)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function CapitalMovementBlock({ flows, onEntityClick, chainId }: {
  flows: Array<{ from: string; to: string; amount: number; fromType: string; toType: string; fromId: string; toId: string; fromWallets?: string[]; toWallets?: string[] }>;
  onEntityClick: (id: string) => void;
  chainId: number;
}) {
  return (
    <div className="rounded-2xl bg-white p-6" data-testid="capital-movement-block">
      <div className="flex items-center gap-3 mb-5">
        <div className="w-8 h-8 flex items-center justify-center">
          <ArrowRight className="w-4 h-4 text-indigo-600" />
        </div>
        <div>
          <h3 className="font-bold text-gray-900">Capital Movement</h3>
          <p className="text-xs text-gray-400">Click any entity to view details</p>
        </div>
      </div>

      <div className="space-y-3">
        {flows.map((flow, i) => (
          <CapitalFlowRow key={i} flow={flow} index={i} onEntityClick={onEntityClick} chainId={chainId} />
        ))}
      </div>
    </div>
  );
}


function CapitalFlowRow({ flow, index, onEntityClick, chainId }: {
  flow: { from: string; to: string; amount: number; fromType: string; toType: string; fromId: string; toId: string; fromWallets?: string[]; toWallets?: string[] };
  index: number;
  onEntityClick: (id: string) => void;
  chainId: number;
}) {
  const [expandedSide, setExpandedSide] = useState<'from' | 'to' | null>(null);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const fromColor = getEntityColor(flow.fromType);
  const toColor = getEntityColor(flow.toType);
  const maxAmount = flow.amount || 1;
  const widthPct = 100;

  const renderWalletList = (wallets: string[], side: string) => (
    <div className="mt-1 ml-6 space-y-0.5 pl-3 border-l-2 border-violet-500/20">
      {wallets.map((addr, i) => (
        <div key={addr} className="flex items-center gap-2 group/w py-0.5" data-testid={`flow-${side}-wallet-${index}-${i}`}>
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
  );

  return (
    <div data-testid={`flow-row-${index + 1}`}>
      <div className="flex items-center gap-3 mb-1.5">
        <div className="min-w-[180px]">
          <button onClick={() => onEntityClick(flow.fromId)}
            className="flex items-center gap-2 hover:bg-gray-50 rounded-lg px-2 py-1 -mx-2 -my-1 transition-colors text-left"
            data-testid={`flow-from-${index + 1}`}>
            <div className={`w-2 h-2 rounded-full flex-shrink-0 ${fromColor.dot}`} />
            <span className="text-sm font-semibold text-gray-900 truncate">{flow.from}</span>
            <span className={`text-[9px] font-bold ${fromColor.text}`}>{typeLabel(flow.fromType)}</span>
          </button>
          {flow.fromWallets && flow.fromWallets.length > 0 && (
            <button
              onClick={() => setExpandedSide(expandedSide === 'from' ? null : 'from')}
              className="ml-4 text-[10px] text-violet-500 hover:text-violet-400 flex items-center gap-0.5 mt-0.5 transition-colors"
              data-testid={`flow-from-expand-${index}`}
            >
              {expandedSide === 'from' ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              {flow.fromWallets.length} wallets
            </button>
          )}
        </div>
        <ArrowRight className="w-4 h-4 text-gray-300 flex-shrink-0" />
        <div className="min-w-[180px]">
          <button onClick={() => onEntityClick(flow.toId)}
            className="flex items-center gap-2 hover:bg-gray-50 rounded-lg px-2 py-1 -mx-2 -my-1 transition-colors text-left"
            data-testid={`flow-to-${index + 1}`}>
            <div className={`w-2 h-2 rounded-full flex-shrink-0 ${toColor.dot}`} />
            <span className="text-sm font-semibold text-gray-900 truncate">{flow.to}</span>
            <span className={`text-[9px] font-bold ${toColor.text}`}>{typeLabel(flow.toType)}</span>
          </button>
          {flow.toWallets && flow.toWallets.length > 0 && (
            <button
              onClick={() => setExpandedSide(expandedSide === 'to' ? null : 'to')}
              className="ml-4 text-[10px] text-violet-500 hover:text-violet-400 flex items-center gap-0.5 mt-0.5 transition-colors"
              data-testid={`flow-to-expand-${index}`}
            >
              {expandedSide === 'to' ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              {flow.toWallets.length} wallets
            </button>
          )}
        </div>
        <span className="ml-auto text-sm font-bold text-gray-700 flex-shrink-0">{fmtUsd(flow.amount)}</span>
      </div>
      {expandedSide === 'from' && flow.fromWallets && renderWalletList(flow.fromWallets, 'from')}
      {expandedSide === 'to' && flow.toWallets && renderWalletList(flow.toWallets, 'to')}
      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden mt-1">
        <div className="h-full rounded-full bg-gradient-to-r from-indigo-400 to-indigo-500 transition-all duration-500" style={{ width: `${widthPct}%` }} />
      </div>
    </div>
  );
}
