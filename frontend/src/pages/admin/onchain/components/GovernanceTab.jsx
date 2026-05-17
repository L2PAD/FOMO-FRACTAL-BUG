/**
 * On-chain Admin — Governance Tab
 * Контроль модели: Drift, Policy, Guardrails, Audit
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  RefreshCw, Activity, Loader2,
} from 'lucide-react';
import { Button } from '../../../../components/ui/button';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function ago(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

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
    <div className={`p-4 rounded-lg ${bg}`}>
      <div className="text-xs text-slate-500 font-medium mb-1">{label}</div>
      <div className={`text-xl font-bold ${color}`}>{value ?? '—'}</div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
  );
}

const ACTION_COLORS = {
  POLICY_ACTIVATED: 'text-emerald-600',
  POLICY_PROPOSED: 'text-blue-600',
  POLICY_ARCHIVED: 'text-slate-500',
  GUARDRAILS_VIOLATION: 'text-amber-600',
  DECISION_MADE: 'text-purple-600',
  MANUAL_OVERRIDE: 'text-red-500',
  PROVIDER_RESET: 'text-slate-500',
};

export default function GovernanceTab({ govState, onRefresh }) {
  const [auditLog, setAuditLog] = useState([]);
  const [policy, setPolicy] = useState(null);
  const [rollingData, setRollingData] = useState(null);
  const [driftData, setDriftData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [auditRes, policyRes, rollingRes, driftRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/v10/onchain-v2/admin/governance/audit?limit=30`).then(r => r.json()),
        fetch(`${API_URL}/api/v10/onchain-v2/admin/governance/policy/active`).then(r => r.json()),
        fetch(`${API_URL}/api/v10/onchain-v2/admin/rolling/ETH?window=30d`).then(r => r.json()),
        fetch(`${API_URL}/api/v10/onchain-v2/admin/drift/ETH`).then(r => r.json()),
      ]);
      if (auditRes.status === 'fulfilled') setAuditLog(auditRes.value?.entries || []);
      if (policyRes.status === 'fulfilled' && policyRes.value?.ok) setPolicy(policyRes.value.policy);
      if (rollingRes.status === 'fulfilled') setRollingData(rollingRes.value);
      if (driftRes.status === 'fulfilled') setDriftData(driftRes.value);
    } catch (e) {
      console.error('Governance fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const doAction = async (action) => {
    setActionLoading(action);
    try {
      const urls = {
        baseline: '/api/v10/onchain-v2/admin/baseline/ETH/score',
        drift: '/api/v10/onchain-v2/admin/drift/ETH',
      };
      const url = urls[action];
      if (url) {
        await fetch(`${API_URL}${url}`, {
          method: action === 'baseline' ? 'POST' : 'GET',
        });
      }
      await fetchData();
      if (onRefresh) onRefresh();
    } catch (e) {
      console.error('Governance action error:', e);
    } finally {
      setActionLoading(null);
    }
  };

  const guardrails = govState?.guardrails;
  const state = govState?.state;
  const driftPsi = guardrails?.driftPsi30d ?? driftData?.psi;
  const rollingScore = rollingData?.score?.avg;

  if (loading && !govState) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="onchain-governance-tab">
      {/* Actions */}
      <div className="flex items-center gap-3 flex-wrap">
        <Button
          variant="outline" size="sm"
          onClick={() => doAction('baseline')}
          disabled={!!actionLoading}
          data-testid="btn-recompute-baseline"
        >
          {actionLoading === 'baseline' ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
          Пересчитать базу
        </Button>
        <Button
          variant="outline" size="sm"
          onClick={() => doAction('drift')}
          disabled={!!actionLoading}
          data-testid="btn-run-drift"
        >
          {actionLoading === 'drift' ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Activity className="w-4 h-4 mr-2" />}
          Проверка дрифта
        </Button>
        <Button variant="outline" size="sm" onClick={() => { fetchData(); if (onRefresh) onRefresh(); }} data-testid="btn-refresh-governance">
          <RefreshCw className="w-4 h-4 mr-2" /> Обновить
        </Button>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <MetricCard
          label="Drift PSI"
          value={driftPsi != null ? driftPsi.toFixed(4) : '—'}
          sub={driftPsi != null && driftPsi > 0.2 ? 'Превышает порог' : driftPsi != null ? 'В норме' : undefined}
          status={driftPsi != null ? (driftPsi > 0.2 ? 'error' : driftPsi > 0.1 ? 'warn' : 'ok') : undefined}
        />
        <MetricCard
          label="Rolling Score (30d)"
          value={rollingScore != null ? rollingScore.toFixed(3) : '—'}
          sub={rollingData?.score ? `std: ${rollingData.score.std?.toFixed(3) || '—'}` : undefined}
          status={rollingScore != null ? 'ok' : undefined}
        />
        <MetricCard
          label="Guardrails"
          value={guardrails?.allPassed ? 'PASS' : 'BLOCK'}
          sub={guardrails?.reasons?.[0] || undefined}
          status={guardrails?.allPassed ? 'ok' : 'error'}
        />
      </div>

      {/* Policy */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Активная политика</h3>
        {policy ? (
          <div className="space-y-4">
            <div className="flex items-center gap-6 text-sm flex-wrap">
              <div><span className="text-slate-500">Имя: </span><span className="text-slate-700 font-medium">{policy.name}</span></div>
              <div><span className="text-slate-500">Версия: </span><span className="text-slate-700">{policy.version}</span></div>
              <div><span className="text-slate-500">Статус: </span><span className="text-emerald-600 font-bold">{policy.status}</span></div>
            </div>
            {policy.weights && (
              <div>
                <div className="text-xs text-slate-500 font-medium mb-2">Веса:</div>
                <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                  {Object.entries(policy.weights).map(([k, v]) => (
                    <div key={k} className="p-2 rounded bg-slate-50/70 text-center">
                      <div className="text-xs text-slate-400 truncate">{k.replace('Weight', '')}</div>
                      <div className="text-sm font-bold text-slate-700">{((v || 0) * 100).toFixed(0)}%</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm text-slate-400 p-4 bg-slate-50/70 rounded-lg">Нет активной политики</div>
        )}
      </section>

      {/* Guardrails detail */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Ограничения</h3>
        {guardrails ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className={`p-3 rounded-lg ${guardrails.providerHealthy ? 'bg-emerald-50/70' : 'bg-red-50/70'}`}>
              <div className="text-xs text-slate-500 font-medium">Провайдер</div>
              <div className={`text-sm font-bold mt-1 ${guardrails.providerHealthy ? 'text-emerald-600' : 'text-red-500'}`}>
                {guardrails.providerHealthy ? 'Здоров' : 'Проблема'}
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-50/70">
              <div className="text-xs text-slate-500 font-medium">Samples 30d</div>
              <div className="text-sm font-bold text-slate-700 mt-1">{guardrails.sampleCount30d ?? '—'}</div>
            </div>
            <div className="p-3 rounded-lg bg-slate-50/70">
              <div className="text-xs text-slate-500 font-medium">Drift PSI 30d</div>
              <div className="text-sm font-bold text-slate-700 mt-1">{guardrails.driftPsi30d?.toFixed(4) ?? '—'}</div>
            </div>
            <div className={`p-3 rounded-lg ${guardrails.crisisFlag ? 'bg-red-50/70' : 'bg-emerald-50/70'}`}>
              <div className="text-xs text-slate-500 font-medium">Кризис</div>
              <div className={`text-sm font-bold mt-1 ${guardrails.crisisFlag ? 'text-red-500' : 'text-emerald-600'}`}>
                {guardrails.crisisFlag ? 'Да' : 'Нет'}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-sm text-slate-400 p-4 bg-slate-50/70 rounded-lg">Данные недоступны</div>
        )}

        {state?.guardrailsViolations?.length > 0 && (
          <div className="mt-3 space-y-1">
            {state.guardrailsViolations.map((v, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-amber-600">
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                <span>{v}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Audit Trail */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Журнал аудита</h3>
        {auditLog.length === 0 ? (
          <div className="text-sm text-slate-400 p-4 bg-slate-50/70 rounded-lg">Нет записей</div>
        ) : (
          <div className="overflow-x-auto bg-slate-50/50 rounded-lg">
            <table className="w-full text-sm" data-testid="audit-trail-table">
              <thead>
                <tr className="text-left text-xs text-slate-500">
                  <th className="py-3 px-4">Время</th>
                  <th className="py-3 px-4">Актор</th>
                  <th className="py-3 px-4">Действие</th>
                  <th className="py-3 px-4">Заметки</th>
                </tr>
              </thead>
              <tbody>
                {auditLog.slice(0, 15).map((entry) => (
                  <tr key={entry.id} className="border-t border-slate-100">
                    <td className="py-2.5 px-4 text-slate-500 whitespace-nowrap">{ago(entry.timestamp)}</td>
                    <td className="py-2.5 px-4 text-slate-600 text-xs">{entry.actor}</td>
                    <td className="py-2.5 px-4">
                      <span className={`text-xs font-bold ${ACTION_COLORS[entry.action] || 'text-slate-500'}`}>
                        {entry.action}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-slate-400 text-xs max-w-xs truncate">
                      {entry.notes || (entry.details ? JSON.stringify(entry.details).slice(0, 60) : '—')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
