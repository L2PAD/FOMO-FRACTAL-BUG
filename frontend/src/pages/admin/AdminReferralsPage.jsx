/**
 * Admin Referrals & Promo Codes Page
 * 
 * Comprehensive management of:
 * - Promo groups (codes, discounts)
 * - Referral system per group
 * - Influencer/blogger management
 * - Referral analytics dashboard
 */

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import AdminLayout from '../../components/admin/AdminLayout';
import {
  Users, CreditCard, Tag, TrendingUp, BarChart3,
  Plus, Trash2, ChevronDown, ChevronRight, Save,
  Loader2, Search, Eye, Award, UserPlus, Copy,
  CheckCircle2, XCircle, RefreshCw, Gift, Percent,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

// ── Tabs ──
const TABS = [
  { id: 'overview', label: 'Обзор', icon: BarChart3 },
  { id: 'promos', label: 'Промокоды', icon: Tag },
  { id: 'referrals', label: 'Рефералы', icon: Users },
  { id: 'influencers', label: 'Инфлюенсеры', icon: Award },
];

// ═══════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════
export default function AdminReferralsPage() {
  const [params, setParams] = useSearchParams();
  const activeTab = params.get('tab') || 'overview';

  const setTab = (t) => setParams({ tab: t });

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2" data-testid="referrals-page-title">
            <Gift className="w-5 h-5 text-indigo-600" />
            Referrals & Promo
          </h1>
          <p className="text-sm text-gray-500 mt-1">Управление промокодами, реферальной системой и инфлюенсерами</p>
        </div>

        {/* Tab nav */}
        <div className="border-b border-gray-200 mb-6">
          <nav className="flex gap-1" data-testid="referrals-tabs">
            {TABS.map(t => {
              const Icon = t.icon;
              return (
                <button key={t.id} onClick={() => setTab(t.id)}
                  data-testid={`ref-tab-${t.id}`}
                  className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === t.id
                      ? 'border-indigo-600 text-indigo-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}>
                  <Icon className="w-4 h-4" />
                  {t.label}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Tab content */}
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'promos' && <PromosTab />}
        {activeTab === 'referrals' && <ReferralsTab />}
        {activeTab === 'influencers' && <InfluencersTab />}
      </div>
    </AdminLayout>
  );
}


// ═══════════════════════════════════════════════════════════════
// OVERVIEW TAB — Dashboard with key metrics
// ═══════════════════════════════════════════════════════════════
function OverviewTab() {
  const [groups, setGroups] = useState([]);
  const [conversions, setConversions] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/api/admin/billing/promos/groups`).then(r => r.ok ? r.json() : { groups: [] }),
      fetch(`${API}/api/admin/billing/promos/referrals`).then(r => r.ok ? r.json() : { conversions: [], total_conversions: 0, total_rewards: 0 }),
    ]).then(([gData, cData]) => {
      setGroups(gData.groups || []);
      setConversions(cData);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState />;

  const totalGroups = groups.length;
  const totalCodes = groups.reduce((s, g) => s + (g.total_codes || 0), 0);
  const usedCodes = groups.reduce((s, g) => s + (g.used_codes || 0), 0);
  const refGroups = groups.filter(g => g.referral_enabled);
  const totalInfluencers = new Set(
    (conversions?.conversions || []).map(c => c.referrer_user_id).filter(Boolean)
  ).size;

  return (
    <div className="space-y-6" data-testid="referrals-overview">
      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Промо-групп" value={totalGroups} icon={Tag} color="text-indigo-600" bg="bg-indigo-50" />
        <KpiCard label="Кодов всего" value={`${usedCodes}/${totalCodes}`} icon={CreditCard} color="text-emerald-600" bg="bg-emerald-50" />
        <KpiCard label="Реферальных групп" value={refGroups.length} icon={Users} color="text-blue-600" bg="bg-blue-50" />
        <KpiCard label="Конверсий" value={conversions?.total_conversions || 0} icon={TrendingUp} color="text-amber-600" bg="bg-amber-50" />
      </div>

      {/* Secondary KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <KpiCard label="Уникальных инфлюенсеров" value={totalInfluencers} icon={Award} color="text-purple-600" bg="bg-purple-50" />
        <KpiCard label="Выплачено вознаграждений" value={`$${(conversions?.total_rewards || 0).toFixed(2)}`} icon={Gift} color="text-rose-600" bg="bg-rose-50" />
        <KpiCard label="Конверсия кодов" value={totalCodes > 0 ? `${((usedCodes / totalCodes) * 100).toFixed(1)}%` : '0%'} icon={Percent} color="text-teal-600" bg="bg-teal-50" />
      </div>

      {/* Active referral groups overview */}
      {refGroups.length > 0 && (
        <div className="border border-gray-200 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Активные реферальные программы</h3>
          <div className="space-y-3">
            {refGroups.map(g => (
              <div key={g.group_id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div className="flex items-center gap-3">
                  <div className="px-2 py-0.5 rounded-full text-xs font-bold bg-blue-100 text-blue-700">
                    REF {g.referral_reward_percent}%
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{g.name}</p>
                    <p className="text-xs text-gray-400">Скидка: {g.discount_percent}% · Коды: {g.used_codes}/{g.total_codes}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-gray-900">{g.referral_conversions || 0}</p>
                  <p className="text-[10px] text-gray-400">конверсий</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent conversions */}
      {(conversions?.conversions || []).length > 0 && (
        <div className="border border-gray-200 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Последние конверсии</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                <th className="pb-2 font-medium">Реферер</th>
                <th className="pb-2 font-medium">Приглашённый</th>
                <th className="pb-2 font-medium">Код</th>
                <th className="pb-2 font-medium">Сумма</th>
                <th className="pb-2 font-medium">Награда</th>
                <th className="pb-2 font-medium">Дата</th>
              </tr>
            </thead>
            <tbody>
              {(conversions.conversions || []).slice(0, 10).map((c, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-2 text-gray-700">{c.referrer_user_id || '—'}</td>
                  <td className="py-2 text-gray-700">{c.referred_user_id || '—'}</td>
                  <td className="py-2 font-mono text-xs text-gray-500">{c.code}</td>
                  <td className="py-2 text-gray-700">${c.payment_amount || 0}</td>
                  <td className="py-2 text-emerald-600 font-medium">${(c.reward_amount || 0).toFixed(2)}</td>
                  <td className="py-2 text-xs text-gray-400">{c.created_at ? new Date(c.created_at).toLocaleDateString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
// PROMOS TAB — Promo Groups & Codes
// ═══════════════════════════════════════════════════════════════
function PromosTab() {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [expandedGroup, setExpandedGroup] = useState(null);
  const [groupCodes, setGroupCodes] = useState({});

  // Create form
  const [newName, setNewName] = useState('');
  const [newDiscount, setNewDiscount] = useState('50');
  const [newCount, setNewCount] = useState('10');
  const [newPrefix, setNewPrefix] = useState('');
  const [newReferralEnabled, setNewReferralEnabled] = useState(false);
  const [newReferralReward, setNewReferralReward] = useState('10');
  const [showCreate, setShowCreate] = useState(false);

  const loadGroups = useCallback(() => {
    setLoading(true);
    fetch(`${API}/api/admin/billing/promos/groups`)
      .then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(d => setGroups(d.groups || []))
      .catch(e => console.error(e))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadGroups(); }, [loadGroups]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const res = await fetch(`${API}/api/admin/billing/promos/groups`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newName,
          discount_percent: parseInt(newDiscount) || 0,
          count: parseInt(newCount) || 10,
          prefix: newPrefix,
          referral_enabled: newReferralEnabled,
          referral_reward_percent: newReferralEnabled ? (parseInt(newReferralReward) || 0) : 0,
        }),
      });
      const data = await res.json();
      if (data.ok) {
        setNewName(''); setNewDiscount('50'); setNewCount('10'); setNewPrefix('');
        setNewReferralEnabled(false); setNewReferralReward('10');
        setShowCreate(false);
        loadGroups();
      }
    } catch { }
    finally { setCreating(false); }
  };

  const handleDelete = async (groupId) => {
    if (!window.confirm('Удалить группу и все её коды?')) return;
    await fetch(`${API}/api/admin/billing/promos/groups/${groupId}`, { method: 'DELETE' });
    loadGroups();
  };

  const loadCodes = async (groupId) => {
    if (expandedGroup === groupId) { setExpandedGroup(null); return; }
    setExpandedGroup(groupId);
    const res = await fetch(`${API}/api/admin/billing/promos/groups/${groupId}/codes`);
    const data = await res.json();
    setGroupCodes(prev => ({ ...prev, [groupId]: data.codes || [] }));
  };

  const copyCode = (code) => {
    navigator.clipboard.writeText(code);
  };

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-6" data-testid="promos-tab">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Промокоды</h3>
          <p className="text-xs text-gray-500 mt-0.5">Создавайте группы промокодов с разными скидками и реферальными настройками</p>
        </div>
        <button onClick={() => setShowCreate(!showCreate)}
          data-testid="create-promo-group-btn"
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-medium hover:bg-indigo-700 transition-colors flex items-center gap-1.5">
          <Plus className="w-3.5 h-3.5" /> Создать группу
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="border border-indigo-200 bg-indigo-50/50 rounded-lg p-5 space-y-4" data-testid="create-promo-form">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="text-xs text-gray-600 font-medium">Название группы</label>
              <input type="text" placeholder="VIP 50%" value={newName}
                onChange={e => setNewName(e.target.value)}
                style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '8px 12px', outline: 'none' }}
                className="mt-1 w-full text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-600 font-medium">Скидка %</label>
              <select value={newDiscount} onChange={e => setNewDiscount(e.target.value)}
                className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                {[0,5,10,15,25,50,75,95,100].map(v => (
                  <option key={v} value={v}>{v === 0 ? '0% (без скидки)' : v === 100 ? '100% (бесплатно)' : `${v}%`}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-600 font-medium">Кол-во кодов</label>
              <input type="number" min="1" max="500" value={newCount}
                onChange={e => setNewCount(e.target.value)}
                style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '8px 12px', outline: 'none' }}
                className="mt-1 w-full text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-600 font-medium">Префикс</label>
              <input type="text" placeholder="VIP" value={newPrefix}
                onChange={e => setNewPrefix(e.target.value.toUpperCase())}
                style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '8px 12px', outline: 'none' }}
                className="mt-1 w-full text-sm font-mono" />
            </div>
          </div>

          {/* Referral toggle */}
          <div className="border-t border-indigo-200 pt-4">
            <div className="flex items-center gap-3 mb-3">
              <button onClick={() => setNewReferralEnabled(!newReferralEnabled)}
                data-testid="referral-toggle-create"
                className={`relative w-10 h-5 rounded-full transition-colors ${newReferralEnabled ? 'bg-indigo-500' : 'bg-gray-300'}`}>
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform shadow-sm ${newReferralEnabled ? 'translate-x-5' : ''}`} />
              </button>
              <span className="text-xs font-medium text-gray-700">Реферальная система</span>
            </div>
            {newReferralEnabled && (
              <div className="ml-13">
                <label className="text-xs text-gray-600 font-medium">Вознаграждение реферера %</label>
                <select value={newReferralReward} onChange={e => setNewReferralReward(e.target.value)}
                  data-testid="referral-reward-select"
                  className="mt-1 w-48 border border-gray-200 rounded-lg px-3 py-2 text-sm">
                  {[5,10,15,20,25,30,40,50].map(v => <option key={v} value={v}>{v}%</option>)}
                </select>
                <p className="text-[10px] text-gray-400 mt-1">% от оплаты приглашённого → вознаграждение рефереру</p>
              </div>
            )}
          </div>

          <button onClick={handleCreate} disabled={creating || !newName.trim()}
            data-testid="submit-promo-group-btn"
            className="px-5 py-2 bg-indigo-600 text-white rounded-lg text-xs font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors">
            {creating ? 'Создание...' : 'Сгенерировать коды'}
          </button>
        </div>
      )}

      {/* Groups list */}
      {groups.length === 0 ? (
        <div className="text-center py-12 text-sm text-gray-400">Нет промо-групп. Создайте первую!</div>
      ) : (
        <div className="space-y-3">
          {groups.map(g => (
            <div key={g.group_id} className="border border-gray-200 rounded-lg overflow-hidden" data-testid={`promo-group-${g.group_id}`}>
              <div className="px-5 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors">
                <div className="flex items-center gap-3">
                  <div className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                    g.discount_percent === 100 ? 'bg-purple-100 text-purple-700'
                    : g.discount_percent >= 50 ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-gray-100 text-gray-700'
                  }`}>
                    {g.discount_percent === 100 ? 'FREE' : `-${g.discount_percent}%`}
                  </div>
                  {g.referral_enabled && (
                    <div className="px-2.5 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-700">
                      REF {g.referral_reward_percent}%
                    </div>
                  )}
                  <div>
                    <p className="text-sm font-medium text-gray-900">{g.name}</p>
                    <p className="text-xs text-gray-400">
                      {g.used_codes}/{g.total_codes} использовано
                      {g.referral_conversions > 0 && ` · ${g.referral_conversions} конверсий`}
                      {' · '}{new Date(g.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => loadCodes(g.group_id)}
                    className="px-3 py-1.5 text-xs font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors flex items-center gap-1">
                    {expandedGroup === g.group_id ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                    Коды
                  </button>
                  <button onClick={() => handleDelete(g.group_id)}
                    className="p-1.5 text-red-400 border border-red-200 rounded-lg hover:bg-red-50 transition-colors">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Expanded codes */}
              {expandedGroup === g.group_id && groupCodes[g.group_id] && (
                <div className="border-t border-gray-100 bg-gray-50 p-4 max-h-60 overflow-y-auto">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    {groupCodes[g.group_id].map(c => (
                      <div key={c.code}
                        className={`font-mono text-xs px-3 py-2 rounded-lg border flex items-center justify-between ${
                          c.used_by ? 'bg-red-50 border-red-200 text-red-500 line-through'
                          : c.referrer_user_id ? 'bg-blue-50 border-blue-200 text-blue-700'
                          : 'bg-white border-gray-200 text-gray-700'
                        }`}>
                        <span>{c.code}</span>
                        {!c.used_by && (
                          <button onClick={() => copyCode(c.code)} className="ml-1 text-gray-300 hover:text-gray-600">
                            <Copy className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
// REFERRALS TAB — Conversions & Tracking
// ═══════════════════════════════════════════════════════════════
function ReferralsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/admin/billing/promos/referrals`)
      .then(r => r.ok ? r.json() : { conversions: [], total_conversions: 0, total_rewards: 0 })
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState />;

  const conversions = data?.conversions || [];

  return (
    <div className="space-y-6" data-testid="referrals-tab">
      {/* KPIs */}
      <div className="grid grid-cols-3 gap-4">
        <KpiCard label="Всего конверсий" value={data?.total_conversions || 0} icon={TrendingUp} color="text-emerald-600" bg="bg-emerald-50" />
        <KpiCard label="Всего вознаграждений" value={`$${(data?.total_rewards || 0).toFixed(2)}`} icon={Gift} color="text-amber-600" bg="bg-amber-50" />
        <KpiCard label="Уникальных рефереров" value={new Set(conversions.map(c => c.referrer_user_id).filter(Boolean)).size} icon={Users} color="text-blue-600" bg="bg-blue-50" />
      </div>

      {/* Conversions table */}
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <div className="px-5 py-3 bg-gray-50 border-b border-gray-200">
          <h3 className="text-sm font-semibold text-gray-900">Журнал конверсий</h3>
        </div>
        {conversions.length === 0 ? (
          <div className="py-12 text-center text-sm text-gray-400">Конверсий пока нет. Они появятся когда приглашённый по реферальному коду оплатит подписку.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b border-gray-100 bg-gray-50">
                <th className="py-2.5 px-4 font-medium">Реферер</th>
                <th className="py-2.5 px-3 font-medium">Приглашённый</th>
                <th className="py-2.5 px-3 font-medium">Код</th>
                <th className="py-2.5 px-3 font-medium">Группа</th>
                <th className="py-2.5 px-3 font-medium">Сумма оплаты</th>
                <th className="py-2.5 px-3 font-medium">Награда</th>
                <th className="py-2.5 px-3 font-medium">Статус</th>
                <th className="py-2.5 px-3 font-medium">Дата</th>
              </tr>
            </thead>
            <tbody>
              {conversions.map((c, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-2.5 px-4 text-gray-700 text-xs">{c.referrer_user_id || '—'}</td>
                  <td className="py-2.5 px-3 text-gray-700 text-xs">{c.referred_user_id || '—'}</td>
                  <td className="py-2.5 px-3 font-mono text-xs text-gray-500">{c.code}</td>
                  <td className="py-2.5 px-3 text-xs text-gray-500">{c.group_id}</td>
                  <td className="py-2.5 px-3 tabular-nums">${c.payment_amount || 0}</td>
                  <td className="py-2.5 px-3 text-emerald-600 font-semibold tabular-nums">${(c.reward_amount || 0).toFixed(2)}</td>
                  <td className="py-2.5 px-3">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      c.status === 'paid' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                    }`}>
                      {c.status === 'paid' ? 'PAID' : 'PENDING'}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-xs text-gray-400">{c.created_at ? new Date(c.created_at).toLocaleDateString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
// Assigned Code Row — with unassign/reassign actions
// ═══════════════════════════════════════════════════════════════
function AssignedCodeRow({ code: c, onRefresh }) {
  const [editing, setEditing] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [busy, setBusy] = useState(false);

  const handleUnassign = async () => {
    if (!window.confirm(`Отвязать код ${c.code}?`)) return;
    setBusy(true);
    try {
      await fetch(`${API}/api/admin/billing/promos/codes/${c.code}/unassign`, { method: 'POST' });
      onRefresh();
    } catch { }
    finally { setBusy(false); }
  };

  const handleReassign = async () => {
    if (!newEmail.trim()) return;
    setBusy(true);
    try {
      const res = await fetch(`${API}/api/admin/billing/promos/codes/${c.code}/reassign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_email: newEmail }),
      });
      const data = await res.json();
      if (data.ok) { setEditing(false); setNewEmail(''); onRefresh(); }
    } catch { }
    finally { setBusy(false); }
  };

  return (
    <>
      <tr className="border-b border-gray-50">
        <td className="py-2.5 px-4 font-mono text-xs font-medium text-gray-700">{c.code}</td>
        <td className="py-2.5 px-3 text-xs text-gray-500">{c.group_name}</td>
        <td className="py-2.5 px-3 text-xs text-gray-700">{c.referrer_user_id}</td>
        <td className="py-2.5 px-3 text-xs">{c.discount_percent}%</td>
        <td className="py-2.5 px-3">
          {c.used_by
            ? <span className="text-[10px] font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded-full">ИСПОЛЬЗОВАН</span>
            : <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">АКТИВЕН</span>}
        </td>
        <td className="py-2.5 px-3">
          {!c.used_by && (
            <div className="flex items-center gap-1">
              <button onClick={() => setEditing(!editing)} disabled={busy}
                className="px-2 py-1 text-[10px] font-medium text-blue-600 border border-blue-200 rounded hover:bg-blue-50 transition-colors">
                {editing ? 'Отмена' : 'Изменить'}
              </button>
              <button onClick={handleUnassign} disabled={busy}
                className="px-2 py-1 text-[10px] font-medium text-red-500 border border-red-200 rounded hover:bg-red-50 transition-colors">
                Отвязать
              </button>
            </div>
          )}
        </td>
      </tr>
      {editing && !c.used_by && (
        <tr className="bg-blue-50/50">
          <td colSpan={6} className="px-4 py-2.5">
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">Переназначить на:</span>
              <input type="email" placeholder="new-email@example.com" value={newEmail}
                onChange={e => setNewEmail(e.target.value)}
                style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '4px 8px', outline: 'none' }}
                className="text-xs w-64" />
              <button onClick={handleReassign} disabled={busy || !newEmail.trim()}
                className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">
                {busy ? 'Saving...' : 'Переназначить'}
              </button>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}


// ═══════════════════════════════════════════════════════════════
// INFLUENCERS TAB — Manage bloggers/influencers
// ═══════════════════════════════════════════════════════════════
function InfluencersTab() {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [assignGroup, setAssignGroup] = useState('');
  const [assignEmail, setAssignEmail] = useState('');
  const [assignResult, setAssignResult] = useState(null);
  const [assigning, setAssigning] = useState(false);
  const [influencers, setInfluencers] = useState([]);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/api/admin/billing/promos/groups`).then(r => r.ok ? r.json() : { groups: [] }),
      fetch(`${API}/api/admin/billing/promos/referrals`).then(r => r.ok ? r.json() : { conversions: [] }),
    ]).then(([gData, cData]) => {
      const refGroups = (gData.groups || []).filter(g => g.referral_enabled);
      setGroups(refGroups);
      if (refGroups.length > 0) setAssignGroup(refGroups[0].group_id);

      // Aggregate influencer stats from conversions
      const convs = cData.conversions || [];
      const influMap = {};
      convs.forEach(c => {
        const uid = c.referrer_user_id;
        if (!uid) return;
        if (!influMap[uid]) influMap[uid] = { user_id: uid, conversions: 0, total_earned: 0, codes: new Set() };
        influMap[uid].conversions += 1;
        influMap[uid].total_earned += c.reward_amount || 0;
        if (c.code) influMap[uid].codes.add(c.code);
      });

      setInfluencers(
        Object.values(influMap)
          .map(inf => ({ ...inf, codes: [...inf.codes] }))
          .sort((a, b) => b.conversions - a.conversions)
      );
    }).finally(() => setLoading(false));
  }, []);

  // Also load assigned codes from all referral groups
  const [assignedCodes, setAssignedCodes] = useState([]);
  useEffect(() => {
    if (groups.length === 0) return;
    Promise.all(
      groups.map(g =>
        fetch(`${API}/api/admin/billing/promos/groups/${g.group_id}/codes`)
          .then(r => r.ok ? r.json() : { codes: [] })
          .then(d => (d.codes || []).filter(c => c.referrer_user_id).map(c => ({ ...c, group_name: g.name })))
      )
    ).then(results => setAssignedCodes(results.flat()));
  }, [groups]);

  const handleAssign = async () => {
    if (!assignEmail.trim() || !assignGroup) return;
    setAssigning(true); setAssignResult(null);
    try {
      const res = await fetch(`${API}/api/admin/billing/promos/groups/${assignGroup}/assign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_email: assignEmail }),
      });
      const data = await res.json();
      setAssignResult(data.ok ? { ok: true, code: data.code } : { ok: false, error: data.detail || 'Error' });
      if (data.ok) setAssignEmail('');
    } catch (e) { setAssignResult({ ok: false, error: e.message }); }
    finally { setAssigning(false); }
  };

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-6" data-testid="influencers-tab">
      {/* Assign code form */}
      <div className="border border-indigo-200 bg-indigo-50/50 rounded-lg p-5" data-testid="assign-influencer-form">
        <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <UserPlus className="w-4 h-4 text-indigo-600" />
          Назначить реферальный код инфлюенсеру
        </h3>
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="text-xs text-gray-600 font-medium">Email пользователя</label>
            <input type="email" placeholder="blogger@example.com" value={assignEmail}
              onChange={e => setAssignEmail(e.target.value)}
              data-testid="influencer-email-input"
              style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '8px 12px', outline: 'none' }}
              className="mt-1 w-full text-sm" />
          </div>
          <div>
            <label className="text-xs text-gray-600 font-medium">Реферальная группа</label>
            <select value={assignGroup} onChange={e => setAssignGroup(e.target.value)}
              data-testid="influencer-group-select"
              className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm min-w-[200px]">
              {groups.map(g => (
                <option key={g.group_id} value={g.group_id}>{g.name} (Скидка {g.discount_percent}% · Награда {g.referral_reward_percent}%)</option>
              ))}
              {groups.length === 0 && <option value="">Нет реферальных групп</option>}
            </select>
          </div>
          <button onClick={handleAssign} disabled={assigning || !assignEmail.trim() || !assignGroup}
            data-testid="assign-influencer-btn"
            className="px-5 py-2 bg-indigo-600 text-white rounded-lg text-xs font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center gap-1.5">
            {assigning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <UserPlus className="w-3.5 h-3.5" />}
            Назначить
          </button>
        </div>
        {assignResult?.ok && (
          <div className="mt-3 flex items-center gap-2 text-sm text-emerald-600">
            <CheckCircle2 className="w-4 h-4" />
            Код <span className="font-mono font-bold">{assignResult.code}</span> назначен
          </div>
        )}
        {assignResult && !assignResult.ok && (
          <div className="mt-3 flex items-center gap-2 text-sm text-red-500">
            <XCircle className="w-4 h-4" /> {assignResult.error}
          </div>
        )}
      </div>

      {/* Assigned codes */}
      {assignedCodes.length > 0 && (
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="px-5 py-3 bg-gray-50 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gray-900">Назначенные коды ({assignedCodes.length})</h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b border-gray-100 bg-gray-50">
                <th className="py-2.5 px-4 font-medium">Код</th>
                <th className="py-2.5 px-3 font-medium">Группа</th>
                <th className="py-2.5 px-3 font-medium">Назначен</th>
                <th className="py-2.5 px-3 font-medium">Скидка</th>
                <th className="py-2.5 px-3 font-medium">Статус</th>
                <th className="py-2.5 px-3 font-medium">Действия</th>
              </tr>
            </thead>
            <tbody>
              {assignedCodes.map(c => (
                <AssignedCodeRow key={c.code} code={c} onRefresh={() => {
                  // Reload assigned codes
                  Promise.all(
                    groups.map(g =>
                      fetch(`${API}/api/admin/billing/promos/groups/${g.group_id}/codes`)
                        .then(r => r.ok ? r.json() : { codes: [] })
                        .then(d => (d.codes || []).filter(cd => cd.referrer_user_id).map(cd => ({ ...cd, group_name: g.name })))
                    )
                  ).then(results => setAssignedCodes(results.flat()));
                }} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Influencer leaderboard */}
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <div className="px-5 py-3 bg-gray-50 border-b border-gray-200">
          <h3 className="text-sm font-semibold text-gray-900">Рейтинг инфлюенсеров</h3>
        </div>
        {influencers.length === 0 ? (
          <div className="py-12 text-center text-sm text-gray-400">Нет данных по инфлюенсерам. Они появятся после первых реферальных конверсий.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b border-gray-100 bg-gray-50">
                <th className="py-2.5 px-4 font-medium">#</th>
                <th className="py-2.5 px-3 font-medium">Инфлюенсер</th>
                <th className="py-2.5 px-3 font-medium">Конверсий</th>
                <th className="py-2.5 px-3 font-medium">Заработано</th>
                <th className="py-2.5 px-3 font-medium">Коды</th>
              </tr>
            </thead>
            <tbody>
              {influencers.map((inf, i) => (
                <tr key={inf.user_id} className="border-b border-gray-50">
                  <td className="py-2.5 px-4 font-bold text-gray-400">{i + 1}</td>
                  <td className="py-2.5 px-3 text-gray-700">{inf.user_id}</td>
                  <td className="py-2.5 px-3 font-semibold text-gray-900">{inf.conversions}</td>
                  <td className="py-2.5 px-3 text-emerald-600 font-semibold">${inf.total_earned.toFixed(2)}</td>
                  <td className="py-2.5 px-3 font-mono text-xs text-gray-500">{inf.codes.join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
// Shared UI
// ═══════════════════════════════════════════════════════════════
function KpiCard({ label, value, icon: Icon, color, bg }) {
  return (
    <div className="border border-gray-200 rounded-lg p-4 flex items-center gap-3">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${bg}`}>
        <Icon className={`w-5 h-5 ${color}`} />
      </div>
      <div>
        <p className="text-lg font-bold text-gray-900">{value}</p>
        <p className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</p>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
      <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Загрузка...
    </div>
  );
}
