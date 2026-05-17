/**
 * Twitter Admin — Governance Tab
 * Управление политиками и пользователями
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Shield, Users, Loader2, RefreshCw, AlertTriangle,
  CheckCircle, Eye, FileText,
} from 'lucide-react';

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
    <div className={`p-4 rounded-lg ${bg}`}>
      <div className="text-xs text-slate-500 font-medium mb-1">{label}</div>
      <div className={`text-lg font-bold ${color}`}>{value ?? '—'}</div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
  );
}

export default function TwitterGovernanceTab() {
  const [users, setUsers] = useState([]);
  const [globalPolicy, setGlobalPolicy] = useState(null);
  const [violations, setViolations] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [usersRes, policyRes, violationsRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/v4/admin/twitter/users`).then(r => r.json()),
        fetch(`${API_URL}/api/v4/admin/twitter/policies/global`).then(r => r.json()),
        fetch(`${API_URL}/api/v4/admin/twitter/policies/violations?limit=20`).then(r => r.json()),
      ]);
      if (usersRes.status === 'fulfilled' && usersRes.value?.ok) setUsers(usersRes.value.data?.users || []);
      if (policyRes.status === 'fulfilled' && policyRes.value?.ok) setGlobalPolicy(policyRes.value.data);
      if (violationsRes.status === 'fulfilled' && violationsRes.value?.ok) setViolations(violationsRes.value.data?.violations || []);
    } catch (e) {
      console.error('Governance fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
      </div>
    );
  }

  const healthyUsers = users.filter(u => u.health === 'HEALTHY' || u.health === 'healthy').length;
  const degradedUsers = users.filter(u => u.health === 'DEGRADED' || u.health === 'WARNING').length;

  return (
    <div className="space-y-8" data-testid="twitter-governance-tab">
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400">Политики, пользователи, нарушения</span>
        <button onClick={fetchData} className="text-slate-400 hover:text-slate-700 transition-colors">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* User stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Всего юзеров"
          value={users.length}
          status={users.length > 0 ? 'ok' : 'warn'}
        />
        <MetricCard
          label="Здоровых"
          value={healthyUsers}
          status={healthyUsers > 0 ? 'ok' : 'warn'}
        />
        <MetricCard
          label="Проблемных"
          value={degradedUsers}
          status={degradedUsers > 0 ? 'warn' : 'ok'}
        />
        <MetricCard
          label="Нарушения"
          value={violations.length}
          status={violations.length > 0 ? 'warn' : 'ok'}
        />
      </div>

      {/* Global Policy */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Глобальная политика</h3>
        {globalPolicy ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {globalPolicy.maxTasksPerHour != null && (
              <div className="p-3 rounded-lg bg-slate-50/70">
                <div className="text-xs text-slate-500 font-medium">Max Tasks/Hour</div>
                <div className="text-sm font-bold text-slate-700 mt-1">{globalPolicy.maxTasksPerHour}</div>
              </div>
            )}
            {globalPolicy.maxPostsPerDay != null && (
              <div className="p-3 rounded-lg bg-slate-50/70">
                <div className="text-xs text-slate-500 font-medium">Max Posts/Day</div>
                <div className="text-sm font-bold text-slate-700 mt-1">{globalPolicy.maxPostsPerDay}</div>
              </div>
            )}
            {globalPolicy.cooldownMinutes != null && (
              <div className="p-3 rounded-lg bg-slate-50/70">
                <div className="text-xs text-slate-500 font-medium">Cooldown</div>
                <div className="text-sm font-bold text-slate-700 mt-1">{globalPolicy.cooldownMinutes}м</div>
              </div>
            )}
            {globalPolicy.maxConcurrentTasks != null && (
              <div className="p-3 rounded-lg bg-slate-50/70">
                <div className="text-xs text-slate-500 font-medium">Max Concurrent</div>
                <div className="text-sm font-bold text-slate-700 mt-1">{globalPolicy.maxConcurrentTasks}</div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm text-slate-400 p-4 bg-slate-50/70 rounded-lg">Политика не загружена</div>
        )}
      </section>

      {/* Users table */}
      {users.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Юзеры — последние {Math.min(users.length, 15)}</h3>
          <div className="overflow-x-auto bg-slate-50/50 rounded-lg">
            <table className="w-full text-sm" data-testid="governance-users-table">
              <thead>
                <tr className="text-left text-xs text-slate-500">
                  <th className="py-3 px-4">Twitter ID</th>
                  <th className="py-3 px-4">Здоровье</th>
                  <th className="py-3 px-4">Задач</th>
                  <th className="py-3 px-4">Последняя задача</th>
                </tr>
              </thead>
              <tbody>
                {users.slice(0, 15).map((u, i) => (
                  <tr key={u.userId || i} className="border-t border-slate-100">
                    <td className="py-2.5 px-4 text-slate-700 font-medium">{u.twitterId || u.userId || '—'}</td>
                    <td className="py-2.5 px-4">
                      <span className={`text-xs font-bold ${u.health === 'HEALTHY' || u.health === 'healthy' ? 'text-emerald-600' : u.health === 'WARNING' ? 'text-amber-600' : 'text-red-500'}`}>
                        {u.health || '—'}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-slate-500">{u.totalTasks ?? '—'}</td>
                    <td className="py-2.5 px-4 text-slate-400 text-xs">{u.lastTaskAt ? new Date(u.lastTaskAt).toLocaleString('ru-RU') : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Violations */}
      {violations.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Нарушения</h3>
          <div className="space-y-2">
            {violations.slice(0, 10).map((v, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-amber-600 p-3 bg-amber-50/50 rounded-lg">
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                <div>
                  <span className="font-medium">{v.userId || v.twitterId || '—'}</span>
                  <span className="text-amber-500 ml-2">{v.reason || v.type || '—'}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
