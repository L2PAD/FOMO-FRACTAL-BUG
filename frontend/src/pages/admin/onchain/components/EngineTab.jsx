/**
 * On-chain Admin — Engine Tab
 * Состояние движка
 */
import React, { useState, useCallback } from 'react';
import {
  Zap, AlertTriangle, Loader2,
  Play, Trash2, RotateCcw,
} from 'lucide-react';
import { Button } from '../../../../components/ui/button';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function MetricCard({ label, value, sub, status }) {
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
    <div className={`p-4 rounded-lg ${bg}`} data-testid={`engine-metric-${label.replace(/\s/g, '-').toLowerCase()}`}>
      <div className="text-xs text-slate-500 font-medium mb-1">{label}</div>
      <div className={`text-lg font-bold ${color}`}>{value ?? '—'}</div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
  );
}

export default function EngineTab({ runtime, loading, onRefresh }) {
  const [actionLoading, setActionLoading] = useState(null);

  const enabled = runtime?.enabled ?? false;
  const provider = runtime?.provider ?? 'unknown';
  const rpcHealthy = runtime?.rpcHealthy ?? false;
  const latestBlock = runtime?.latestBlock;
  const notes = runtime?.notes || [];

  const engineMode = !enabled ? 'OFF' : provider === 'mock' ? 'SNAPSHOT' : 'LIVE';
  const modeColor =
    engineMode === 'LIVE' ? 'text-emerald-600'
    : engineMode === 'SNAPSHOT' ? 'text-amber-600'
    : 'text-red-500';

  const doAction = useCallback(async (action) => {
    setActionLoading(action);
    try {
      const endpoints = {
        'run': '/api/v10/onchain-v2/admin/snapshot/tick',
        'flush': '/api/v10/onchain-v2/admin/governance/policy/dry-run',
      };
      const url = endpoints[action];
      if (url) {
        await fetch(`${API_URL}${url}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: action === 'flush' ? JSON.stringify({
            weights: {}, thresholds: {}, guardrails: {}
          }) : undefined,
        });
      }
      if (onRefresh) onRefresh();
    } catch (e) {
      console.error('Engine action error:', e);
    } finally {
      setActionLoading(null);
    }
  }, [onRefresh]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="onchain-engine-tab">
      {/* Engine Mode banner */}
      <div className="flex items-center gap-3">
        <Zap className={`w-5 h-5 ${modeColor}`} />
        <span className={`text-lg font-bold ${modeColor}`}>
          Режим: {engineMode}
        </span>
      </div>

      {/* Row 1 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Режим"
          value={engineMode}
          sub={provider !== 'unknown' ? provider.toUpperCase() : undefined}
          status={engineMode === 'LIVE' ? 'ok' : engineMode === 'SNAPSHOT' ? 'warn' : 'error'}
        />
        <MetricCard
          label="Последний блок"
          value={latestBlock?.toLocaleString() ?? '—'}
          status={latestBlock ? 'ok' : 'warn'}
        />
        <MetricCard
          label="Провайдер"
          value={provider !== 'unknown' ? provider.toUpperCase() : '—'}
          sub={rpcHealthy ? 'RPC OK' : 'RPC недоступен'}
          status={rpcHealthy ? 'ok' : 'error'}
        />
        <MetricCard
          label="Ошибки"
          value={notes.length}
          status={notes.length > 0 ? 'warn' : 'ok'}
        />
      </div>

      {/* Row 2 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="RPC настроен"
          value={runtime?.rpcConfigured ? 'Да' : 'Нет'}
          status={runtime?.rpcConfigured ? 'ok' : 'warn'}
        />
        <MetricCard
          label="Провайдер инициализирован"
          value={runtime?.providerInitialized ? 'Да' : 'Нет'}
          status={runtime?.providerInitialized ? 'ok' : 'warn'}
        />
        <MetricCard
          label="Fallback"
          value={provider === 'mock' ? 'Да (MOCK)' : 'Нет'}
          status={provider === 'mock' ? 'warn' : 'ok'}
        />
        <MetricCard
          label="Здоровье RPC"
          value={rpcHealthy ? 'OK' : 'DOWN'}
          status={rpcHealthy ? 'ok' : 'error'}
        />
      </div>

      {/* Notes / Warnings */}
      {notes.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-700 mb-2">Примечания</h3>
          <div className="space-y-1">
            {notes.map((note, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-amber-600">
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                <span>{note}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Действия</h3>
        <div className="flex items-center gap-3 flex-wrap">
          <Button
            variant="outline" size="sm"
            onClick={() => doAction('run')}
            disabled={!!actionLoading}
            data-testid="btn-run-engine"
          >
            {actionLoading === 'run' ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
            Запустить движок
          </Button>
          <Button
            variant="outline" size="sm"
            onClick={() => doAction('flush')}
            disabled={!!actionLoading}
            data-testid="btn-flush-cache"
          >
            {actionLoading === 'flush' ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Trash2 className="w-4 h-4 mr-2" />}
            Сбросить кеш
          </Button>
          <Button
            variant="outline" size="sm"
            onClick={onRefresh}
            disabled={!!actionLoading}
            data-testid="btn-refresh-engine"
          >
            <RotateCcw className="w-4 h-4 mr-2" /> Обновить
          </Button>
        </div>
      </div>
    </div>
  );
}
