import React from 'react';
import { Building2, Landmark, Wallet } from 'lucide-react';
import type { ActorItem } from '../types/smartMoney';

export function fmtUsd(n: number): string {
  if (!n || !Number.isFinite(n)) return '$0';
  const abs = Math.abs(n);
  if (abs >= 1e9) return `$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `$${(abs / 1e3).toFixed(0)}K`;
  return `$${abs.toFixed(0)}`;
}

export function fmtUsdSigned(n: number): string {
  if (!n || !Number.isFinite(n)) return '$0';
  const sign = n >= 0 ? '+' : '-';
  return `${sign}${fmtUsd(n)}`;
}

export function shortAddr(addr: string): string {
  if (!addr || addr.length < 10) return addr;
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}

export function isAddress(s: string): boolean {
  return s.startsWith('0x') && s.length >= 40;
}

export function cleanName(n: string): string {
  return n.replace(/_/g, ' ');
}

export function displayName(item: ActorItem): string {
  if (item.entityName && !item.entityName.toLowerCase().includes('unknown')) {
    return cleanName(item.entityName);
  }
  const t = item.entityType.toLowerCase();
  if (t === 'whale') return 'Large wallet';
  if (t === 'dex') return 'DEX aggregator';
  if (t === 'protocol') return 'Protocol contract';
  if (isAddress(item.entityId)) return `Wallet ${shortAddr(item.entityId)}`;
  if (item.trades > 10000) return 'High-frequency wallet';
  if (Math.abs(item.netUsd) > 1e6) return 'Large wallet';
  return 'Unlabeled wallet';
}

export function typeLabel(type: string): string {
  const map: Record<string, string> = {
    exchange: 'Exchange', cex: 'Exchange', protocol: 'Protocol', dex: 'DEX',
    whale: 'Whale', smart_money: 'Smart Money', bridge: 'Bridge', fund: 'Fund',
    unknown: 'Wallet', EXCHANGE: 'Exchange', PROTOCOL: 'Protocol', DEX: 'DEX',
    WHALE: 'Whale', SMART_MONEY: 'Smart Money', BRIDGE: 'Bridge', FUND: 'Fund', UNKNOWN: 'Wallet',
  };
  return map[type] || 'Wallet';
}

export function getEntityColor(type: string): { dot: string; text: string; bg: string } {
  const t = (type || '').toLowerCase();
  if (t === 'whale' || t === 'smart_money') return { dot: 'bg-purple-500', text: 'text-purple-400', bg: 'bg-purple-500/10' };
  if (t === 'exchange' || t === 'cex') return { dot: 'bg-amber-500', text: 'text-amber-400', bg: 'bg-amber-500/10' };
  if (t === 'protocol' || t === 'dex') return { dot: 'bg-blue-500', text: 'text-blue-400', bg: 'bg-blue-500/10' };
  if (t === 'bridge') return { dot: 'bg-cyan-500', text: 'text-cyan-400', bg: 'bg-cyan-500/10' };
  return { dot: 'bg-gray-500', text: 'text-gray-400', bg: 'bg-gray-500/10' };
}

export function getEntityIcon(type: string) {
  const t = (type || '').toLowerCase();
  if (t === 'exchange' || t === 'cex') return <Building2 className="w-4 h-4" />;
  if (t === 'protocol' || t === 'dex') return <Landmark className="w-4 h-4" />;
  return <Wallet className="w-4 h-4" />;
}

export function activityScore(item: ActorItem): { label: string; color: string } {
  const vol = Math.abs(item.netUsd);
  if (item.trades > 5000 || vol > 5_000_000) return { label: 'High activity', color: 'text-emerald-600' };
  if (item.trades > 500 || vol > 500_000) return { label: 'Medium activity', color: 'text-amber-600' };
  return { label: 'Low activity', color: 'text-gray-500' };
}

export function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text);
}

export function sortItems(items: ActorItem[], by: 'flow' | 'volume' | 'trades'): ActorItem[] {
  return [...items].sort((a, b) => {
    if (by === 'volume') return (Math.abs(b.dexUsd) + Math.abs(b.cexUsd)) - (Math.abs(a.dexUsd) + Math.abs(a.cexUsd));
    if (by === 'trades') return b.trades - a.trades;
    return Math.abs(b.netUsd) - Math.abs(a.netUsd);
  });
}

export function timeSince(date: Date | null): string {
  if (!date) return '---';
  const s = Math.floor((Date.now() - date.getTime()) / 1000);
  if (s < 5) return 'just now';
  if (s < 60) return `${s}s ago`;
  return `${Math.floor(s / 60)}m ago`;
}

export function deriveCapitalFlows(buyers: ActorItem[], sellers: ActorItem[], walletLookup?: Record<string, string[]>): Array<{
  from: string; to: string; amount: number; fromType: string; toType: string;
  fromId: string; toId: string; fromWallets?: string[]; toWallets?: string[];
}> {
  const flows: Array<{
    from: string; to: string; amount: number; fromType: string; toType: string;
    fromId: string; toId: string; fromWallets?: string[]; toWallets?: string[];
  }> = [];
  const topSellers = sellers.filter(s => s.netUsd < 0).slice(0, 5);
  const topBuyers = buyers.filter(b => b.netUsd > 0).slice(0, 5);
  for (const seller of topSellers) {
    for (const buyer of topBuyers) {
      if (seller.entityId === buyer.entityId) continue;
      const overlapAmount = Math.min(Math.abs(seller.netUsd), buyer.netUsd);
      if (overlapAmount > 10000) {
        flows.push({
          from: displayName(seller), to: displayName(buyer),
          amount: overlapAmount, fromType: seller.entityType, toType: buyer.entityType,
          fromId: seller.entityId, toId: buyer.entityId,
          fromWallets: walletLookup?.[seller.entityId] || walletLookup?.[seller.entityName || ''] || [],
          toWallets: walletLookup?.[buyer.entityId] || walletLookup?.[buyer.entityName || ''] || [],
        });
      }
    }
  }
  flows.sort((a, b) => b.amount - a.amount);
  return flows.slice(0, 6);
}

export function generateInsight(totalBuy: number, totalSell: number, buyers: ActorItem[], sellers: ActorItem[]): {
  title: string; body: string; action: string; signal: 'bullish' | 'bearish' | 'neutral';
} {
  const net = totalBuy + totalSell;
  const ratio = totalBuy > 0 ? Math.abs(totalSell) / totalBuy : 1;
  const topBuyer = buyers.find(b => b.netUsd > 0);
  const topSeller = sellers.find(s => s.netUsd < 0);
  if (net > 0 && ratio < 0.7) {
    return {
      title: 'Strong accumulation detected',
      body: `Smart money is aggressively accumulating through DEX. ${topBuyer ? `${displayName(topBuyer)} added ${fmtUsdSigned(topBuyer.netUsd)}.` : ''} Net inflow significantly exceeds outflow.`,
      action: 'Monitor for breakout. Consider long entry on pullback.',
      signal: 'bullish',
    };
  }
  if (net < 0 && ratio > 1.5) {
    return {
      title: 'Distribution pressure building',
      body: `Large entities are reducing positions. ${topSeller ? `${displayName(topSeller)} moved ${fmtUsd(Math.abs(topSeller.netUsd))}.` : ''} Selling pressure outweighs buying.`,
      action: 'Caution on new longs. Watch for support breakdown.',
      signal: 'bearish',
    };
  }
  return {
    title: 'Mixed signals from smart money',
    body: `Buying and selling are roughly balanced. ${topBuyer ? `${displayName(topBuyer)} accumulating ${fmtUsdSigned(topBuyer.netUsd)}` : ''}, while ${topSeller ? `${displayName(topSeller)} distributing ${fmtUsd(Math.abs(topSeller?.netUsd || 0))}` : 'sellers are active'}.`,
    action: 'Wait for clear directional bias before entering.',
    signal: 'neutral',
  };
}

export function computeSmartMoneyIndex(totalBuy: number, totalSell: number): { score: number; confidence: number } {
  const total = totalBuy + Math.abs(totalSell);
  if (total === 0) return { score: 50, confidence: 0 };
  const ratio = totalBuy / total;
  const score = Math.round(ratio * 100);
  const confidence = Math.min(95, Math.round((total / 50_000_000) * 100));
  return { score, confidence };
}
