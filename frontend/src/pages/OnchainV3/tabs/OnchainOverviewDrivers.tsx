/**
 * Market Drivers Section — On-chain v3 Overview
 * ===============================================
 * 
 * P0.1: Migrated from legacy MarketHub DriversTab.
 * Shows signal drivers A-F for the selected network,
 * embedded directly in the Overview tab.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  ArrowLeftRight,
  Layers,
  GitBranch,
  Droplets,
  Users,
  Bell,
  Info,
  X,
  RefreshCw,
  Loader2,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Minus,
  Shield,
  Clock,
} from 'lucide-react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

// ── Driver metadata (from signal.meta.js) ──

const DRIVER_CODES = ['A', 'B', 'C', 'D', 'E', 'F'] as const;
type DriverCode = typeof DRIVER_CODES[number];

const DRIVER_META: Record<DriverCode, { title: string; icon: React.ElementType; description: string }> = {
  A: { title: 'Exchange Pressure', icon: ArrowLeftRight, description: 'Tracks flows between exchanges and wallets.' },
  B: { title: 'Accumulation Zones', icon: Layers, description: 'Identifies price levels where smart money accumulated.' },
  C: { title: 'Corridors', icon: GitBranch, description: 'Detects repeated capital flow patterns.' },
  D: { title: 'Liquidity', icon: Droplets, description: 'Monitors liquidity across DEX pools.' },
  E: { title: 'Smart Actors', icon: Users, description: 'Tracks wallets with historically profitable patterns.' },
  F: { title: 'Events', icon: Bell, description: 'Unusual on-chain activity and new interactions.' },
};

const STATE_BG: Record<string, string> = {
  ACCUMULATION: 'text-emerald-700',
  SUPPORT: 'text-emerald-700',
  PERSISTENT: 'text-emerald-700',
  GROWING: 'text-emerald-700',
  ACCUMULATING: 'text-emerald-700',
  ACTIVE: 'text-blue-700',
  DISTRIBUTION: 'text-red-700',
  RESISTANCE: 'text-red-700',
  SCATTERED: 'text-red-700',
  SHRINKING: 'text-red-700',
  DISTRIBUTING: 'text-red-700',
  ALERT: 'text-amber-700',
  NEUTRAL: 'text-gray-600',
  STABLE: 'text-gray-600',
  QUIET: 'text-gray-600',
};

const STRENGTH_BAR: Record<string, { w: string; color: string; label: string }> = {
  HIGH: { w: '100%', color: 'bg-emerald-500', label: 'Strong' },
  MEDIUM: { w: '66%', color: 'bg-amber-500', label: 'Moderate' },
  LOW: { w: '33%', color: 'bg-gray-300', label: 'Weak' },
};

const DECISION_STYLE: Record<string, { bg: string; text: string }> = {
  BUY: { bg: '', text: 'text-emerald-700' },
  SELL: { bg: '', text: 'text-red-700' },
  NEUTRAL: { bg: '', text: 'text-gray-700' },
};

// ── Types ──

interface Driver {
  key: string;
  state: string;
  strength: string;
  summary: string;
}

interface DriversData {
  asset: string;
  network: string;
  decision: string;
  quality: string;
  confidence: string;
  drivers: Record<string, Driver>;
  timestamp: number;
  guardrails?: {
    blocked: boolean;
    blockedBy: string[];
    originalDecision: string;
  };
}

// ── Mini Signal Card ──

function MiniDriverCard({ code, driver }: { code: DriverCode; driver: Driver }) {
  const [showInfo, setShowInfo] = useState(false);
  const meta = DRIVER_META[code];
  const Icon = meta.icon;
  const stateStyle = STATE_BG[driver.state] || STATE_BG.NEUTRAL;
  const strength = STRENGTH_BAR[driver.strength] || STRENGTH_BAR.LOW;

  return (
    <div
      className={`relative rounded-xl p-4 transition-all ${stateStyle}`}
      data-testid={`driver-card-${code}`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4" />
          <span className="text-xs font-medium opacity-60">Driver {code}</span>
          <span className="font-semibold text-sm">{meta.title}</span>
        </div>
        <button
          onClick={() => setShowInfo(!showInfo)}
          className="w-5 h-5 rounded-full bg-white/60 flex items-center justify-center hover:bg-white"
        >
          <Info className="w-3 h-3 opacity-50" />
        </button>
      </div>

      <div className="flex items-center gap-2 mb-2">
        <span className="w-1.5 h-1.5 rounded-full bg-current" />
        <span className="text-xs font-medium">{driver.state}</span>
      </div>

      <div className="mb-2">
        <div className="flex items-center justify-between mb-0.5">
          <span className="text-[10px] opacity-50">Strength</span>
          <span className="text-[10px] font-medium opacity-60">{strength.label}</span>
        </div>
        <div className="h-1 bg-black/10 rounded-full overflow-hidden">
          <div
            className={`h-full ${strength.color} rounded-full transition-all duration-500`}
            style={{ width: strength.w }}
          />
        </div>
      </div>

      <p className="text-xs opacity-70 leading-relaxed line-clamp-2">{driver.summary}</p>

      {showInfo && (
        <div className="absolute inset-0 bg-white rounded-xl p-4 z-10">
          <div className="flex items-center justify-between mb-2">
            <span className="font-semibold text-gray-900 text-sm">{meta.title}</span>
            <button onClick={() => setShowInfo(false)} className="hover:bg-gray-100 rounded-full p-0.5">
              <X className="w-3.5 h-3.5 text-gray-400" />
            </button>
          </div>
          <p className="text-xs text-gray-600">{meta.description}</p>
        </div>
      )}
    </div>
  );
}

// ── Main Component ──

export function OnchainOverviewDrivers() {
  const [data, setData] = useState<DriversData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const network = 'ethereum';

  const fetchDrivers = useCallback(async (isRefresh = false) => {
    try {
      if (!isRefresh) setLoading(true);
      setError(null);
      const res = await fetch(`${API_BASE}/api/v3/signals/market/${network}`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const json = await res.json();
      if (json.ok && json.data) {
        setData(json.data);
      } else {
        setError('No driver data');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load drivers');
    } finally {
      setLoading(false);
    }
  }, [network]);

  useEffect(() => {
    fetchDrivers();
  }, [fetchDrivers]);

  if (loading) {
    return (
      <div className="rounded-2xl bg-white p-6" data-testid="market-drivers-section">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-4 h-4 text-blue-500" />
          <span className="text-sm font-semibold text-gray-700">Market Drivers</span>
        </div>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-2xl bg-white p-6" data-testid="market-drivers-section">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-4 h-4 text-blue-500" />
          <span className="text-sm font-semibold text-gray-700">Market Drivers</span>
        </div>
        <div className="text-center py-8">
          <AlertTriangle className="w-8 h-8 text-gray-400 mx-auto mb-2" />
          <p className="text-sm text-gray-500">{error || 'No data available'}</p>
          <button
            onClick={() => fetchDrivers()}
            className="mt-3 text-sm text-blue-600 hover:underline"
            data-testid="market-drivers-retry"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const decisionStyle = DECISION_STYLE[data.decision] || DECISION_STYLE.NEUTRAL;
  const DecisionIcon = data.decision === 'BUY' ? TrendingUp : data.decision === 'SELL' ? TrendingDown : Minus;
  const isBlocked = data.guardrails?.blocked;

  const formatTime = (ts: number) => {
    const diff = Date.now() - ts;
    if (diff < 60000) return 'just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    return `${Math.floor(diff / 3600000)}h ago`;
  };

  return (
    <div className="rounded-2xl bg-white p-6" data-testid="market-drivers-section">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-blue-500" />
          <span className="text-sm font-semibold text-gray-700">Market Drivers</span>
          <span className="text-xs text-gray-400 uppercase">{data.network}</span>
        </div>
        <div className="flex items-center gap-3">
          {/* Decision badge */}
          <div className={`flex items-center gap-1.5 px-3 py-1 rounded-lg ${decisionStyle.bg}`}>
            <DecisionIcon className={`w-3.5 h-3.5 ${decisionStyle.text}`} />
            <span className={`text-xs font-bold ${decisionStyle.text}`}>{data.decision}</span>
          </div>
          {/* Quality */}
          <div className="flex items-center gap-1 text-xs text-gray-500">
            <Shield className="w-3.5 h-3.5" />
            {data.quality}
          </div>
          {/* Time */}
          <div className="flex items-center gap-1 text-xs text-gray-400">
            <Clock className="w-3 h-3" />
            {formatTime(data.timestamp)}
          </div>
          {/* Refresh */}
          <button
            onClick={() => fetchDrivers(true)}
            className="p-1 rounded hover:bg-gray-100 transition-colors"
            data-testid="market-drivers-refresh"
          >
            <RefreshCw className="w-3.5 h-3.5 text-gray-400" />
          </button>
        </div>
      </div>

      {/* Guardrails warning */}
      {isBlocked && (
        <div className="flex items-center gap-2 mb-4 px-3 py-2 text-xs text-amber-700">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          <span>
            Decision blocked: {data.guardrails?.blockedBy?.join(', ')}
          </span>
        </div>
      )}

      {/* Driver Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3" data-testid="market-drivers-grid">
        {DRIVER_CODES.map(code => {
          const driver = data.drivers[code];
          if (!driver) return null;
          return <MiniDriverCard key={code} code={code} driver={driver} />;
        })}
      </div>
    </div>
  );
}

export default OnchainOverviewDrivers;
