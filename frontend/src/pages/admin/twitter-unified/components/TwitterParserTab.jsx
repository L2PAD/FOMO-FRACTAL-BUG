/**
 * Twitter Admin — Parser Tab
 * Парсер: аккаунты, сессии, слоты, мониторинг
 * НЕ ЛОМАЕМ ИНФРАСТРУКТУРУ — только обзор + ссылки на детальные страницы
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Users, Key, Layers, Activity, Loader2, RefreshCw,
  CheckCircle, XCircle, AlertTriangle, ArrowRight,
} from 'lucide-react';
import { api } from '../../../../api/client';

function MetricCard({ label, value, sub, status, link }) {
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

  const Content = (
    <div className={`p-4 rounded-lg ${bg} ${link ? 'hover:ring-1 hover:ring-slate-300 transition-all cursor-pointer' : ''}`}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-slate-500 font-medium">{label}</span>
        {link && <ArrowRight className="w-3 h-3 text-slate-400" />}
      </div>
      <div className={`text-lg font-bold ${color}`}>{value ?? '—'}</div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
  );

  if (link) {
    return <Link to={link} data-testid={`parser-link-${label.replace(/\s/g, '-').toLowerCase()}`}>{Content}</Link>;
  }
  return Content;
}

export default function TwitterParserTab() {
  const [accounts, setAccounts] = useState(null);
  const [sessions, setSessions] = useState(null);
  const [slots, setSlots] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [accRes, sessRes, slotsRes] = await Promise.allSettled([
        api.get('/api/admin/twitter-parser/accounts').then(r => r.data),
        api.get('/api/admin/twitter-parser/sessions').then(r => r.data),
        api.get('/api/admin/twitter-parser/slots').then(r => r.data),
      ]);
      if (accRes.status === 'fulfilled') setAccounts(accRes.value);
      if (sessRes.status === 'fulfilled') setSessions(sessRes.value);
      if (slotsRes.status === 'fulfilled') setSlots(slotsRes.value);
    } catch (e) {
      console.error('Parser fetch error:', e);
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

  const accList = accounts?.accounts || [];
  const sessList = sessions?.sessions || [];
  const slotsList = slots?.slots || [];

  const activeAccounts = accList.filter(a => a.status === 'ACTIVE').length;
  const validSessions = sessList.filter(s => s.status === 'OK' || s.status === 'VALID').length;
  const staleSessions = sessList.filter(s => s.status === 'STALE').length;
  const enabledSlots = slotsList.filter(s => s.enabled).length;

  return (
    <div className="space-y-8" data-testid="twitter-parser-tab">
      {/* Refresh */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400">Парсер инфраструктура — обзор</span>
        <button onClick={fetchData} className="text-slate-400 hover:text-slate-700 transition-colors">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Key Metrics — clickable cards linking to detailed pages */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Аккаунты"
          value={`${activeAccounts} / ${accList.length}`}
          sub="Активных / Всего"
          status={activeAccounts > 0 ? 'ok' : 'warn'}
          link="/admin/twitter-parser/accounts"
        />
        <MetricCard
          label="Сессии"
          value={`${validSessions} / ${sessList.length}`}
          sub={staleSessions > 0 ? `Stale: ${staleSessions}` : 'Все валидны'}
          status={validSessions > 0 ? 'ok' : sessList.length > 0 ? 'warn' : 'error'}
          link="/admin/twitter-parser/sessions"
        />
        <MetricCard
          label="Слоты"
          value={`${enabledSlots} / ${slotsList.length}`}
          sub="Включённых / Всего"
          status={enabledSlots > 0 ? 'ok' : 'warn'}
          link="/admin/twitter-parser/slots"
        />
        <MetricCard
          label="Мониторинг"
          value="Перейти"
          sub="Real-time мониторинг"
          link="/admin/twitter-parser/monitor"
        />
      </div>

      {/* Accounts summary */}
      {accList.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Аккаунты</h3>
          <div className="overflow-x-auto bg-slate-50/50 rounded-lg">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500">
                  <th className="py-3 px-4">Имя</th>
                  <th className="py-3 px-4">Статус</th>
                  <th className="py-3 px-4">Тип</th>
                </tr>
              </thead>
              <tbody>
                {accList.slice(0, 10).map((acc, i) => (
                  <tr key={acc._id || i} className="border-t border-slate-100">
                    <td className="py-2.5 px-4 text-slate-700 font-medium">{acc.username || acc.name || `Account ${i + 1}`}</td>
                    <td className="py-2.5 px-4">
                      <span className={`text-xs font-bold ${acc.status === 'ACTIVE' ? 'text-emerald-600' : acc.status === 'DISABLED' ? 'text-slate-400' : 'text-red-500'}`}>
                        {acc.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-slate-500">{acc.type || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Sessions summary */}
      {sessList.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Последние сессии</h3>
          <div className="overflow-x-auto bg-slate-50/50 rounded-lg">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500">
                  <th className="py-3 px-4">ID</th>
                  <th className="py-3 px-4">Статус</th>
                  <th className="py-3 px-4">Risk</th>
                </tr>
              </thead>
              <tbody>
                {sessList.slice(0, 8).map((s, i) => (
                  <tr key={s._id || i} className="border-t border-slate-100">
                    <td className="py-2.5 px-4 text-slate-700 font-medium text-xs">{(s._id || s.id || '').slice(-8)}</td>
                    <td className="py-2.5 px-4">
                      <span className={`text-xs font-bold ${s.status === 'OK' || s.status === 'VALID' ? 'text-emerald-600' : s.status === 'STALE' ? 'text-amber-600' : 'text-red-500'}`}>
                        {s.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-slate-500">{s.riskScore ?? s.risk ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
