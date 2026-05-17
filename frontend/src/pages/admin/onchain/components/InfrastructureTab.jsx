/**
 * On-chain Admin — Infrastructure Tab
 * RPC Pool, Mode Switcher, Indexer Diagnostics, Snapshot Builder
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Server, RefreshCw, Loader2, Zap, Play, Power,
  Activity, AlertTriangle, CheckCircle, XCircle, Database,
} from 'lucide-react';
import { Button } from '../../../../components/ui/button';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const CHAIN_LABELS = { ethereum: 'ETH', arbitrum: 'ARB', optimism: 'OP', base: 'BASE' };
const CHAIN_COLORS = {
  ethereum: 'bg-blue-100 text-blue-700',
  arbitrum: 'bg-sky-100 text-sky-700',
  optimism: 'bg-red-100 text-red-700',
  base: 'bg-indigo-100 text-indigo-700',
};

function HealthIcon({ status }) {
  if (status === 'ok' || status === 'connected' || status === 'synced')
    return <CheckCircle className="w-4 h-4 text-emerald-500" />;
  if (status === 'syncing' || status === 'lite')
    return <Activity className="w-4 h-4 text-amber-500 animate-pulse" />;
  if (status === 'error' || status === 'degraded')
    return <XCircle className="w-4 h-4 text-red-500" />;
  return <AlertTriangle className="w-4 h-4 text-slate-400" />;
}

function StatusBadge({ status }) {
  const colors = {
    connected: 'bg-emerald-100 text-emerald-700',
    synced: 'bg-emerald-100 text-emerald-700',
    syncing: 'bg-amber-100 text-amber-700',
    lite: 'bg-blue-100 text-blue-700',
    error: 'bg-red-100 text-red-700',
    paused: 'bg-slate-100 text-slate-600',
    idle: 'bg-slate-100 text-slate-500',
    ok: 'bg-emerald-100 text-emerald-700',
    degraded: 'bg-amber-100 text-amber-700',
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${colors[status] || 'bg-slate-100 text-slate-500'}`}>
      <HealthIcon status={status} />
      {status?.toUpperCase() || 'UNKNOWN'}
    </span>
  );
}

export default function InfrastructureTab({ runtime }) {
  const [rpcData, setRpcData] = useState(null);
  const [indexerData, setIndexerData] = useState(null);
  const [diagnostics, setDiagnostics] = useState(null);
  const [snapshotData, setSnapshotData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [rpc, indexer, diag, snapshot] = await Promise.allSettled([
        fetch(`${API_URL}/api/v10/onchain-v2/admin/rpc`).then(r => r.json()),
        fetch(`${API_URL}/api/admin/indexer/status`).then(r => r.json()),
        fetch(`${API_URL}/api/admin/indexer/diagnostics`).then(r => r.json()),
        fetch(`${API_URL}/api/v10/onchain-v2/admin/snapshot/backfill-metrics`).then(r => r.json()),
      ]);
      if (rpc.status === 'fulfilled') setRpcData(rpc.value);
      if (indexer.status === 'fulfilled' && indexer.value.ok) setIndexerData(indexer.value);
      if (diag.status === 'fulfilled' && diag.value.ok) setDiagnostics(diag.value);
      if (snapshot.status === 'fulfilled') setSnapshotData(snapshot.value);
    } catch (e) {
      console.error('Infrastructure fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); const id = setInterval(fetchAll, 15_000); return () => clearInterval(id); }, [fetchAll]);

  const setMode = async (mode) => {
    setActionLoading(`mode-${mode}`);
    try {
      await fetch(`${API_URL}/api/admin/indexer/mode`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      await fetchAll();
    } finally { setActionLoading(null); }
  };

  const doAction = async (url) => {
    setActionLoading(url);
    try {
      await fetch(`${API_URL}${url}`, { method: 'POST' });
      await fetchAll();
    } finally { setActionLoading(null); }
  };

  if (loading && !diagnostics) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
      </div>
    );
  }

  const rpcConfig = rpcData?.config;
  const rpcHealth = rpcData?.health;
  const endpoints = rpcConfig?.endpoints || [];
  const healthMap = {};
  (rpcHealth?.endpoints || []).forEach(h => { healthMap[h.id] = h; });

  const indexer = indexerData?.indexer || {};
  const currentMode = diagnostics?.mode || indexer?.mode || 'unknown';
  const isIndexer = currentMode === 'indexer';
  const isLite = currentMode === 'preview' || currentMode === 'lite';

  return (
    <div className="space-y-8" data-testid="onchain-infrastructure-tab">
      {/* Mode Switcher */}
      <section data-testid="mode-switcher">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <Power className="w-4 h-4" /> Режим индексера
          </h3>
          <Button variant="outline" size="sm" onClick={fetchAll} disabled={!!actionLoading} data-testid="btn-refresh-infra">
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} /> Обновить
          </Button>
        </div>

        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={() => setMode('LIMITED')}
            disabled={!!actionLoading}
            data-testid="btn-mode-lite"
            className={`px-5 py-2.5 rounded-lg text-sm font-semibold transition-all border-2 ${
              isLite ? 'bg-blue-600 text-white border-blue-600 shadow-lg shadow-blue-600/20' : 'bg-white text-slate-600 border-slate-200 hover:border-blue-300'
            }`}
          >
            {actionLoading === 'mode-LIMITED' && <Loader2 className="w-3 h-3 mr-1.5 animate-spin inline" />}
            LITE
          </button>
          <button
            onClick={() => setMode('FULL')}
            disabled={!!actionLoading}
            data-testid="btn-mode-indexer"
            className={`px-5 py-2.5 rounded-lg text-sm font-semibold transition-all border-2 ${
              isIndexer ? 'bg-emerald-600 text-white border-emerald-600 shadow-lg shadow-emerald-600/20' : 'bg-white text-slate-600 border-slate-200 hover:border-emerald-300'
            }`}
          >
            {actionLoading === 'mode-FULL' && <Loader2 className="w-3 h-3 mr-1.5 animate-spin inline" />}
            INDEXER
          </button>
        </div>

        <div className="flex items-center gap-6 text-xs text-slate-500">
          <span>
            Режим: <span className={`font-bold ${isIndexer ? 'text-emerald-600' : 'text-blue-600'}`}>{currentMode.toUpperCase()}</span>
          </span>
          <span>
            Статус: <StatusBadge status={indexer.runtimeStatus === 'RUNNING' ? (isIndexer ? 'syncing' : 'connected') : 'paused'} />
          </span>
          <span>
            RPC: <StatusBadge status={diagnostics?.health?.rpc || 'idle'} />
          </span>
        </div>
      </section>

      {/* Indexer Diagnostics */}
      {diagnostics && (
        <section data-testid="indexer-diagnostics">
          <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4" /> Диагностика индексера
          </h3>

          {/* Health Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            {Object.entries(diagnostics.health || {}).map(([key, status]) => (
              <div key={key} className="flex items-center gap-2 p-3 rounded-lg bg-slate-50/70" data-testid={`health-${key}`}>
                <HealthIcon status={status} />
                <div>
                  <div className="text-xs text-slate-500 capitalize">{key}</div>
                  <div className="text-xs font-bold text-slate-700">{status.toUpperCase()}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Chain Sync */}
          <div className="overflow-x-auto bg-slate-50/50 rounded-lg mb-4">
            <table className="w-full text-sm" data-testid="chain-sync-table">
              <thead>
                <tr className="text-left text-xs text-slate-500">
                  <th className="py-3 px-4">Сеть</th>
                  <th className="py-3 px-4">Последний блок</th>
                  <th className="py-3 px-4">Head</th>
                  <th className="py-3 px-4">Lag</th>
                  <th className="py-3 px-4">Статус</th>
                  <th className="py-3 px-4">Блоков/мин</th>
                  <th className="py-3 px-4">Транзакций/мин</th>
                  <th className="py-3 px-4">Событий/мин</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(diagnostics.chains || {}).map(([chain, data]) => {
                  const metrics = diagnostics.ingestion?.chains?.[chain] || {};
                  return (
                    <tr key={chain} className="border-t border-slate-100">
                      <td className="py-2.5 px-4">
                        <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${CHAIN_COLORS[chain] || 'bg-slate-100 text-slate-600'}`}>
                          {CHAIN_LABELS[chain] || chain}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-slate-700 font-mono text-xs">{data.last_block?.toLocaleString()}</td>
                      <td className="py-2.5 px-4 text-slate-500 font-mono text-xs">{data.head_block?.toLocaleString()}</td>
                      <td className="py-2.5 px-4">
                        <span className={`font-bold text-xs ${data.lag > 20 ? 'text-red-500' : data.lag > 5 ? 'text-amber-600' : 'text-emerald-600'}`}>
                          {data.lag}
                        </span>
                      </td>
                      <td className="py-2.5 px-4"><StatusBadge status={data.status} /></td>
                      <td className="py-2.5 px-4 text-slate-600 text-xs">{metrics.blocks_per_min || 0}</td>
                      <td className="py-2.5 px-4 text-slate-600 text-xs">{metrics.tx_per_min || 0}</td>
                      <td className="py-2.5 px-4 text-slate-600 text-xs">{metrics.events_per_min || 0}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Ingestion Totals */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 rounded-lg bg-slate-50/70 flex items-center gap-3" data-testid="total-blocks">
              <Database className="w-5 h-5 text-slate-400" />
              <div>
                <div className="text-xs text-slate-500">Блоков</div>
                <div className="text-lg font-bold text-slate-700">{diagnostics.ingestion?.totals?.blocks?.toLocaleString() || 0}</div>
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-50/70 flex items-center gap-3" data-testid="total-txs">
              <Zap className="w-5 h-5 text-slate-400" />
              <div>
                <div className="text-xs text-slate-500">Транзакций</div>
                <div className="text-lg font-bold text-slate-700">{diagnostics.ingestion?.totals?.transactions?.toLocaleString() || 0}</div>
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-50/70 flex items-center gap-3" data-testid="total-events">
              <Activity className="w-5 h-5 text-slate-400" />
              <div>
                <div className="text-xs text-slate-500">Событий</div>
                <div className="text-lg font-bold text-slate-700">{diagnostics.ingestion?.totals?.events?.toLocaleString() || 0}</div>
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-50/70 flex items-center gap-3" data-testid="total-entity-activity">
              <Server className="w-5 h-5 text-slate-400" />
              <div>
                <div className="text-xs text-slate-500">Entity Activity</div>
                <div className="text-lg font-bold text-slate-700">{diagnostics.ingestion?.totals?.entity_activity?.toLocaleString() || 0}</div>
              </div>
            </div>
          </div>

          {/* Entity Resolution */}
          {diagnostics.entity_resolution && (
            <div className="mt-4 p-4 rounded-lg bg-indigo-50/50 border border-indigo-100" data-testid="entity-resolution-panel">
              <h4 className="text-xs font-semibold text-indigo-700 mb-2">Address Resolution</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div>
                  <span className="text-slate-500">Адресов в кэше:</span>
                  <span className="ml-1.5 font-bold text-slate-700">{diagnostics.entity_resolution.address_labels_loaded}</span>
                </div>
                <div>
                  <span className="text-slate-500">Сущностей:</span>
                  <span className="ml-1.5 font-bold text-slate-700">{diagnostics.entity_resolution.entities_loaded}</span>
                </div>
                <div>
                  <span className="text-slate-500">Обогащённых tx:</span>
                  <span className="ml-1.5 font-bold text-emerald-600">{diagnostics.entity_resolution.enriched_transactions?.toLocaleString()}</span>
                </div>
                <div>
                  <span className="text-slate-500">Entity activity:</span>
                  <span className="ml-1.5 font-bold text-emerald-600">{diagnostics.entity_resolution.entity_activity_records?.toLocaleString()}</span>
                </div>
              </div>
            </div>
          )}
        </section>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3 flex-wrap">
        <Button variant="outline" size="sm" onClick={() => doAction('/api/v10/onchain-v2/admin/snapshot/tick')} disabled={!!actionLoading} data-testid="btn-force-snapshot">
          <Zap className="w-4 h-4 mr-2" /> Force Snapshot
        </Button>
        <Button variant="outline" size="sm" onClick={() => doAction('/api/admin/indexer/restart')} disabled={!!actionLoading} data-testid="btn-restart-indexer">
          <Play className="w-4 h-4 mr-2" /> Перезапуск индексера
        </Button>
      </div>

      {/* RPC Pool */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
          <Server className="w-4 h-4" /> RPC Pool
        </h3>
        <div className="text-xs text-slate-400 mb-3">
          Здоровых: <span className="font-bold text-slate-600">{rpcHealth?.healthyCount ?? 0}</span> / {rpcHealth?.totalCount ?? 0}
          <span className="mx-2">|</span>
          Средн. задержка: <span className="font-bold text-slate-600">{rpcHealth?.avgLatencyMs?.toFixed(0) ?? '—'}ms</span>
        </div>
        {endpoints.length > 0 && (
          <div className="overflow-x-auto bg-slate-50/50 rounded-lg">
            <table className="w-full text-sm" data-testid="rpc-pool-table">
              <thead>
                <tr className="text-left text-xs text-slate-500">
                  <th className="py-3 px-4">Провайдер</th>
                  <th className="py-3 px-4">Сеть</th>
                  <th className="py-3 px-4">Статус</th>
                  <th className="py-3 px-4">Задержка</th>
                  <th className="py-3 px-4">Вес</th>
                </tr>
              </thead>
              <tbody>
                {endpoints.map(ep => {
                  const h = healthMap[ep.id];
                  return (
                    <tr key={ep.id} className="border-t border-slate-100">
                      <td className="py-2.5 px-4 text-slate-700 font-medium">{ep.provider}</td>
                      <td className="py-2.5 px-4 text-slate-500">{ep.chainName}</td>
                      <td className="py-2.5 px-4"><StatusBadge status={h?.healthy ? 'ok' : 'error'} /></td>
                      <td className="py-2.5 px-4 text-slate-500">{h?.latencyMs ? `${h.latencyMs}ms` : '—'}</td>
                      <td className="py-2.5 px-4 text-slate-500">{ep.weight}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Snapshot / Backfill */}
      {snapshotData && (
        <section>
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Snapshot / Backfill</h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-lg bg-slate-50/70">
              <div className="text-xs text-slate-500 font-medium">Всего снимков</div>
              <div className="text-lg font-bold text-slate-700 mt-1">{snapshotData.totalSnapshots ?? '—'}</div>
            </div>
            <div className="p-4 rounded-lg bg-slate-50/70">
              <div className="text-xs text-slate-500 font-medium">Backfill</div>
              <div className="text-lg font-bold text-slate-700 mt-1">{snapshotData.backfillStatus ?? '—'}</div>
            </div>
            <div className="p-4 rounded-lg bg-slate-50/70">
              <div className="text-xs text-slate-500 font-medium">Ошибки</div>
              <div className={`text-lg font-bold mt-1 ${(snapshotData.errors ?? 0) > 0 ? 'text-red-500' : 'text-slate-700'}`}>
                {snapshotData.errors ?? 0}
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
