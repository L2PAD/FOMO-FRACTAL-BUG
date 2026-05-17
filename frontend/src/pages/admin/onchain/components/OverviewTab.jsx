/**
 * On-chain Admin — Overview Tab
 * Операционный центр: "On-chain работает или сломан?"
 */
import React from 'react';
import {
  Activity, Server, Database, CheckCircle,
  AlertTriangle, Clock, Zap, Shield, Layers,
} from 'lucide-react';

// ────────────────────────────────────────
function StatusDot({ ok }) {
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full ${ok ? 'bg-emerald-500' : 'bg-red-500'}`}
      data-testid={`status-dot-${ok ? 'ok' : 'error'}`}
    />
  );
}

// ────────────────────────────────────────
function MetricCard({ label, value, sub, icon: Icon, status }) {
  const color =
    status === 'ok' ? 'text-emerald-600'
    : status === 'warn' ? 'text-amber-600'
    : status === 'error' ? 'text-red-500'
    : 'text-slate-700';

  const bg =
    status === 'ok' ? 'bg-emerald-50/70'
    : status === 'warn' ? 'bg-amber-50/70'
    : status === 'error' ? 'bg-red-50/70'
    : 'bg-slate-50/70';

  return (
    <div className={`p-4 rounded-lg ${bg}`} data-testid={`metric-${label.replace(/\s/g, '-').toLowerCase()}`}>
      <div className="flex items-center gap-2 mb-2">
        {Icon && <Icon className={`w-4 h-4 ${color}`} />}
        <span className="text-xs text-slate-500 font-medium">{label}</span>
      </div>
      <div className={`text-lg font-bold ${color}`}>{value ?? '—'}</div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
  );
}

// ────────────────────────────────────────
function FlagRow({ name, enabled }) {
  return (
    <div className="flex items-center justify-between py-2.5" data-testid={`flag-${name}`}>
      <span className="text-sm text-slate-600">{name}</span>
      <span className={`text-xs font-bold px-2 py-0.5 rounded ${enabled ? 'text-emerald-700 bg-emerald-50' : 'text-slate-400 bg-slate-50'}`}>
        {enabled ? 'ON' : 'OFF'}
      </span>
    </div>
  );
}

// ────────────────────────────────────────
export default function OverviewTab({ runtime, govState, indexerStatus, loading }) {
  const enabled = runtime?.enabled ?? false;
  const rpcHealthy = runtime?.rpcHealthy ?? false;
  const provider = runtime?.provider ?? 'unknown';
  const latestBlock = runtime?.latestBlock;
  const guardrailsPass = govState?.guardrails?.allPassed ?? false;
  const policyVersion = govState?.activePolicy?.version ?? '—';
  const driftPsi = govState?.guardrails?.driftPsi30d;

  const indexer = indexerStatus?.indexer || {};
  const indexerRunning = indexer.runtimeStatus === 'RUNNING';
  const indexerLag = indexer.behindBlocks ?? null;

  const systemOk = enabled && rpcHealthy && guardrailsPass;
  const systemLabel = !enabled ? 'OFFLINE' : systemOk ? 'HEALTHY' : 'DEGRADED';
  const systemColor =
    systemLabel === 'HEALTHY' ? 'text-emerald-600'
    : systemLabel === 'DEGRADED' ? 'text-amber-600'
    : 'text-red-500';

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Activity className="w-5 h-5 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="onchain-overview-tab">
      {/* System Health banner */}
      <div className="flex items-center gap-3">
        <StatusDot ok={systemOk} />
        <span className={`text-lg font-bold ${systemColor}`}>{systemLabel}</span>
      </div>

      {/* Row 1: Core metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Здоровье системы"
          value={systemLabel}
          icon={Activity}
          status={systemOk ? 'ok' : enabled ? 'warn' : 'error'}
        />
        <MetricCard
          label="RPC"
          value={rpcHealthy ? 'OK' : 'DOWN'}
          sub={provider !== 'unknown' ? provider.toUpperCase() : undefined}
          icon={Server}
          status={rpcHealthy ? 'ok' : 'error'}
        />
        <MetricCard
          label="Индексатор"
          value={indexerLag != null ? `${indexerLag} блоков` : '—'}
          sub={indexerRunning ? 'Работает' : 'Остановлен'}
          icon={Database}
          status={indexerRunning ? 'ok' : 'warn'}
        />
        <MetricCard
          label="Последний блок"
          value={latestBlock?.toLocaleString() ?? '—'}
          icon={Layers}
          status={latestBlock ? 'ok' : 'warn'}
        />
      </div>

      {/* Row 2: Engine & Governance */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Движок"
          value={enabled ? 'ACTIVE' : 'OFF'}
          icon={Zap}
          status={enabled ? 'ok' : 'error'}
        />
        <MetricCard
          label="Drift PSI"
          value={driftPsi != null ? driftPsi.toFixed(3) : '—'}
          sub={driftPsi != null && driftPsi > 0.2 ? 'Выше порога' : driftPsi != null ? 'В норме' : undefined}
          icon={AlertTriangle}
          status={driftPsi != null ? (driftPsi > 0.2 ? 'error' : driftPsi > 0.1 ? 'warn' : 'ok') : undefined}
        />
        <MetricCard
          label="Нарушения"
          value={govState?.state?.guardrailsViolations?.length ?? 0}
          icon={Shield}
          status={(govState?.state?.guardrailsViolations?.length ?? 0) > 0 ? 'warn' : 'ok'}
        />
        <MetricCard
          label="Политика"
          value={`v${policyVersion}`}
          icon={CheckCircle}
          status={govState?.activePolicy ? 'ok' : 'warn'}
        />
      </div>

      {/* System Flags */}
      <div>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Системные флаги</h3>
        <div className="rounded-lg bg-slate-50/70 p-4 divide-y divide-slate-100">
          <FlagRow name="ONCHAIN_ENABLED" enabled={enabled} />
          <FlagRow name="SNAPSHOT_MODE" enabled={provider === 'mock'} />
          <FlagRow name="INDEXER_ENABLED" enabled={indexerRunning} />
          <FlagRow name="DRIFT_GUARD" enabled={govState?.guardrails?.allPassed ?? false} />
          <FlagRow name="ENGINE_ENABLED" enabled={enabled && rpcHealthy} />
        </div>
      </div>
    </div>
  );
}
