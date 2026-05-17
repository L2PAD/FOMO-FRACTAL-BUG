/**
 * System Status Strip — On-chain v3 Health Bar
 * ==============================================
 * 
 * Phase 0: System Visibility
 * Compact bar showing aggregated on-chain health status.
 * Fetches from /api/health/onchain.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Activity, AlertTriangle, CheckCircle, XCircle, RefreshCw, ChevronDown, ChevronUp, Clock } from 'lucide-react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

interface JobHealth {
  status: 'ok' | 'degraded' | 'critical' | 'missing' | 'stale' | 'idle';
  lastRun: string | null;
  lagMs: number | null;
  running: boolean;
  tickCount?: number;
  successCount?: number;
  errorCount?: number;
  lastError?: string | null;
}

interface HealthData {
  ok: boolean;
  status: 'OK' | 'DEGRADED' | 'CRITICAL';
  mongo: string;
  timestamp: number;
  subsystems: Record<string, Record<string, JobHealth>>;
}

const STATUS_CONFIG = {
  OK: { bg: 'bg-emerald-50', text: 'text-emerald-700', icon: CheckCircle, label: 'All Systems OK' },
  DEGRADED: { bg: 'bg-amber-50', text: 'text-amber-700', icon: AlertTriangle, label: 'Degraded' },
  CRITICAL: { bg: 'bg-red-50', text: 'text-red-700', icon: XCircle, label: 'Critical' },
};

const JOB_STATUS_DOT: Record<string, string> = {
  ok: 'bg-emerald-500',
  degraded: 'bg-amber-500',
  critical: 'bg-red-500',
  missing: 'bg-gray-400',
  stale: 'bg-amber-400',
  idle: 'bg-gray-400',
};

function formatLag(ms: number | null) {
  if (ms == null) return 'never';
  if (ms < 60_000) return `${Math.floor(ms / 1000)}s ago`;
  if (ms < 3600_000) return `${Math.floor(ms / 60_000)}m ago`;
  return `${Math.floor(ms / 3600_000)}h ago`;
}

export function SystemStatusStrip() {
  const [data, setData] = useState<HealthData | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/health/onchain`);
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch {} finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30_000); // refresh every 30s
    return () => clearInterval(interval);
  }, [fetchHealth]);

  if (loading || !data) return null;

  const cfg = STATUS_CONFIG[data.status] || STATUS_CONFIG.CRITICAL;
  const StatusIcon = cfg.icon;

  // Count problems
  const problems: { group: string; job: string; status: string }[] = [];
  for (const [group, jobs] of Object.entries(data.subsystems)) {
    for (const [job, health] of Object.entries(jobs)) {
      if (health.status !== 'ok') {
        problems.push({ group, job, status: health.status });
      }
    }
  }

  return (
    <div className={`rounded-xl ${cfg.bg} transition-all`} data-testid="system-status-strip">
      {/* Compact bar */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-2"
        data-testid="status-strip-toggle"
      >
        <div className="flex items-center gap-2">
          <StatusIcon className={`w-4 h-4 ${cfg.text}`} />
          <span className={`text-xs font-semibold ${cfg.text}`}>{cfg.label}</span>
          {problems.length > 0 && (
            <span className={`text-[10px] ${cfg.text} opacity-70`}>
              ({problems.length} issue{problems.length > 1 ? 's' : ''}: {problems.map(p => p.job).join(', ')})
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {/* Quick dots for subsystems */}
          <div className="flex items-center gap-1">
            {Object.entries(data.subsystems).map(([group, jobs]) => {
              const worstStatus = Object.values(jobs).reduce((worst, j) => {
                if (j.status === 'critical' || worst === 'critical') return 'critical';
                if (j.status === 'degraded' || worst === 'degraded') return 'degraded';
                return j.status;
              }, 'ok' as string);
              return (
                <div key={group} className="flex items-center gap-0.5" title={group}>
                  <span className={`w-1.5 h-1.5 rounded-full ${JOB_STATUS_DOT[worstStatus] || JOB_STATUS_DOT.missing}`} />
                </div>
              );
            })}
          </div>
          <span className="text-[10px] text-gray-400">
            {data.mongo === 'connected' ? 'DB OK' : 'DB DOWN'}
          </span>
          <RefreshCw
            className="w-3 h-3 text-gray-400 cursor-pointer hover:text-gray-600"
            onClick={(e) => { e.stopPropagation(); fetchHealth(); }}
          />
          {expanded ? <ChevronUp className="w-3.5 h-3.5 text-gray-400" /> : <ChevronDown className="w-3.5 h-3.5 text-gray-400" />}
        </div>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-4 pb-3 border-t border-current/10" data-testid="status-strip-details">
          <div className="grid grid-cols-5 gap-3 mt-2">
            {Object.entries(data.subsystems).map(([group, jobs]) => (
              <div key={group} className="rounded-lg bg-white/60 p-2.5">
                <div className="text-[10px] uppercase tracking-wider text-gray-500 font-bold mb-1.5">{group}</div>
                {Object.entries(jobs).map(([jobName, health]) => (
                  <div key={jobName} className="flex items-center justify-between py-0.5" title={health.lastError || ''}>
                    <div className="flex items-center gap-1.5">
                      <span className={`w-1.5 h-1.5 rounded-full ${JOB_STATUS_DOT[health.status]}`} />
                      <span className="text-[10px] text-gray-700">{jobName}</span>
                      {health.running && <Activity className="w-2.5 h-2.5 text-blue-500 animate-pulse" />}
                      {(health.errorCount ?? 0) > 0 && (
                        <span className="text-[9px] text-red-500 font-mono">{health.errorCount}err</span>
                      )}
                    </div>
                    <span className="text-[10px] text-gray-400">{formatLag(health.lagMs)}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default SystemStatusStrip;
