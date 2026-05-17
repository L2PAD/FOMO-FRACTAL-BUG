/**
 * Deviations Mode — Signals Tab, On-chain v3
 * =============================================
 * 
 * P0.2: Migrated from legacy MarketHub DiscoveryTab.
 * Shows emerging signals / deviation watchlist.
 * Rendered as a mode within the Signals tab.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Target,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Flame,
  ChevronRight,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

// ── Types ──

interface DeviationToken {
  symbol: string;
  tokenAddress?: string;
  address?: string;
  score?: number;
  type?: string;
  deviation?: string;
  reason?: string;
  decisionImpact?: string;
  change24h?: number;
}

interface DeviationsResponse {
  ok: boolean;
  data: {
    tokens: DeviationToken[];
    checkedCount: number;
    window: string;
    interpretation: {
      headline: string;
      description: string;
    };
    analyzedAt: string;
  };
}

interface ActiveToken {
  symbol?: string;
  token?: string;
  tokenAddress?: string;
  reason?: string;
  type?: string;
  decisionImpact?: string;
}

// ── Impact badge ──

function ImpactBadge({ impact }: { impact?: string }) {
  if (!impact || impact === 'NONE') return null;
  const styles: Record<string, string> = {
    HIGH: 'bg-red-50 text-red-700',
    MEDIUM: 'bg-amber-50 text-amber-700',
    LOW: 'bg-blue-50 text-blue-700',
  };
  const labels: Record<string, string> = { HIGH: 'Affects Decision', MEDIUM: 'May Affect', LOW: 'Watched' };
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${styles[impact] || ''}`}>
      {labels[impact] || impact}
    </span>
  );
}

// ── Deviation Row ──

function DeviationRow({ item }: { item: DeviationToken }) {
  const scorePct = item.score != null ? `${Math.round(item.score * 100)}%` : null;
  return (
    <div
      className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
      data-testid={`deviation-row-${item.symbol}`}
    >
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center">
          <Target className="w-4 h-4 text-blue-500" />
        </div>
        <div>
          <div className="font-medium text-gray-900 text-sm">{item.symbol || 'Unknown'}</div>
          <div className="text-xs text-gray-500">{item.deviation || item.type || item.reason || ''}</div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <ImpactBadge impact={item.decisionImpact} />
        {scorePct && <span className="text-xs font-medium text-gray-600">{scorePct}</span>}
        <ChevronRight className="w-4 h-4 text-gray-300" />
      </div>
    </div>
  );
}

// ── Activity Row ──

function ActivityRow({ item }: { item: ActiveToken }) {
  return (
    <div
      className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
      data-testid={`activity-row-${item.symbol || item.token}`}
    >
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-orange-50 flex items-center justify-center">
          <Flame className="w-4 h-4 text-orange-500" />
        </div>
        <div>
          <div className="font-medium text-gray-900 text-sm">{item.symbol || item.token || 'Unknown'}</div>
          <div className="text-xs text-gray-500">{item.reason || item.type || ''}</div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <ImpactBadge impact={item.decisionImpact} />
        <ChevronRight className="w-4 h-4 text-gray-300" />
      </div>
    </div>
  );
}

// ── Main Component ──

export function SignalsDeviationsMode() {
  const [deviations, setDeviations] = useState<DeviationsResponse | null>(null);
  const [activity, setActivity] = useState<ActiveToken[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async (isRefresh = false) => {
    try {
      if (!isRefresh) setLoading(true);
      setError(null);

      const [devRes, actRes] = await Promise.all([
        fetch(`${API_BASE}/api/market/emerging-signals?limit=10`).then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`${API_BASE}/api/market/top-active-tokens?limit=10&window=24h`).then(r => r.ok ? r.json() : null).catch(() => null),
      ]);

      if (devRes) setDeviations(devRes);
      if (actRes) {
        const items = actRes?.data?.items || actRes?.items || [];
        setActivity(items);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load deviations');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="space-y-4" data-testid="deviations-mode">
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
        </div>
      </div>
    );
  }

  const devTokens = deviations?.data?.tokens || [];
  const interpretation = deviations?.data?.interpretation;
  const hasDeviations = devTokens.length > 0;
  const hasActivity = activity.length > 0;

  return (
    <div className="space-y-6" data-testid="deviations-mode">
      {/* Interpretation banner */}
      {interpretation && (
        <div className="rounded-xl bg-gray-50 p-4">
          <div className="text-sm font-medium text-gray-800">{interpretation.headline}</div>
          <div className="text-xs text-gray-500 mt-1">{interpretation.description}</div>
          {deviations?.data?.analyzedAt && (
            <div className="text-[10px] text-gray-400 mt-2">
              Analyzed: {new Date(deviations.data.analyzedAt).toLocaleTimeString()}
              {' · '}{deviations.data.checkedCount} tokens checked
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Deviation Watchlist */}
        <div className="rounded-xl bg-white overflow-hidden" data-testid="deviation-watchlist">
          <div className="px-4 py-3 bg-gray-50 flex items-center gap-2">
            <Target className="w-4 h-4 text-blue-500" />
            <span className="text-sm font-semibold text-gray-800">Deviation Watchlist</span>
            <span className="ml-auto text-xs text-gray-400">{devTokens.length}</span>
          </div>
          {hasDeviations ? (
            <div>
              {devTokens.slice(0, 8).map((item, i) => (
                <DeviationRow key={`${item.symbol}-${i}`} item={item} />
              ))}
            </div>
          ) : (
            <div className="p-8 text-center text-sm text-gray-500">
              No deviations detected
            </div>
          )}
        </div>

        {/* Unusual Activity */}
        <div className="rounded-xl bg-white overflow-hidden" data-testid="unusual-activity">
          <div className="px-4 py-3 bg-gray-50 flex items-center gap-2">
            <Flame className="w-4 h-4 text-orange-500" />
            <span className="text-sm font-semibold text-gray-800">Unusual Activity</span>
            <span className="ml-auto text-xs text-gray-400">{activity.length}</span>
          </div>
          {hasActivity ? (
            <div>
              {activity.slice(0, 8).map((item, i) => (
                <ActivityRow key={`${item.symbol || item.token}-${i}`} item={item} />
              ))}
            </div>
          ) : (
            <div className="p-8 text-center text-sm text-gray-500">
              No unusual activity detected
            </div>
          )}
        </div>
      </div>

      {/* Refresh button */}
      <div className="flex justify-center">
        <button
          onClick={() => fetchData(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 text-sm transition-colors"
          data-testid="deviations-refresh"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh Deviations
        </button>
      </div>
    </div>
  );
}

export default SignalsDeviationsMode;
