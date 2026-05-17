/**
 * NEWS ADMIN PAGE
 * 
 * Управление новостным парсером и источниками.
 * Sub-tabs: Обзор | Источники | Здоровье | События
 * 
 * APIs:
 *   GET /api/admin/news/health
 *   GET /api/admin/news/sources
 *   GET /api/admin/news/events?limit=N
 */

import React, { useState, useEffect, useCallback, memo } from 'react';
import {
  Activity, AlertTriangle, BarChart2, CheckCircle, Clock, Database,
  ExternalLink, FileText, Globe, Loader2, Newspaper, Play, RefreshCw,
  Rss, Search, Server, X, XCircle, Zap, Shield, Eye, Gauge
} from 'lucide-react';
import { AdminLayout } from '../../components/admin/PlatformAdminLayout';
import { InfoTooltip } from '../../components/admin/InfoTooltip';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// ── Sub-Tabs ────────────────────────────────────────────────────
const TABS = [
  { id: 'overview', label: 'Обзор', icon: Activity },
  { id: 'sources', label: 'Источники', icon: Database },
  { id: 'health', label: 'Здоровье', icon: CheckCircle },
  { id: 'events', label: 'События', icon: FileText },
];

// ── Color System ────────────────────────────────────────────────
const c = {
  text: '#0f172a',
  textSecondary: '#475569',
  textMuted: '#94a3b8',
  accent: '#6366f1',
  accentSoft: '#eef2ff',
  border: '#e2e8f0',
  surface: '#f8fafc',
  success: '#16a34a',
  successSoft: '#dcfce7',
  warning: '#d97706',
  warningSoft: '#fef3c7',
  danger: '#dc2626',
  dangerSoft: '#fee2e2',
};

const tierColors = {
  A: { bg: '#ecfdf5', text: '#059669', label: 'Основной' },
  B: { bg: '#eef2ff', text: '#4f46e5', label: 'Вторичный' },
  C: { bg: '#fef3c7', text: '#d97706', label: 'Агрегатор' },
};

// ── Format Helpers ──────────────────────────────────────────────
function timeAgo(dateStr) {
  if (!dateStr) return '—';
  const d = Date.now() - new Date(dateStr).getTime();
  if (d < 60000) return 'только что';
  if (d < 3600000) return `${Math.floor(d / 60000)} мин назад`;
  if (d < 86400000) return `${Math.floor(d / 3600000)} ч назад`;
  return `${Math.floor(d / 86400000)} д назад`;
}

// ── Section Header ──────────────────────────────────────────────
function SectionHeader({ title, tooltip, action }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        <h3 className="text-lg font-semibold" style={{ color: c.text }}>{title}</h3>
        {tooltip && <InfoTooltip text={tooltip} />}
      </div>
      {action}
    </div>
  );
}

// ── Velocity Level Config ────────────────────────────────────────
const VELOCITY_LEVELS = {
  CALM: { label: 'Тихий рынок', color: c.textMuted, bg: c.surface, icon: '○' },
  NORMAL: { label: 'Нормальный поток', color: c.success, bg: c.successSoft, icon: '●' },
  ELEVATED: { label: 'Повышенная активность', color: c.warning, bg: c.warningSoft, icon: '◉' },
  SPIKE: { label: 'Всплеск активности', color: c.danger, bg: c.dangerSoft, icon: '◉' },
};

// ── Velocity Block (Admin) ──────────────────────────────────────
const VelocityBlock = memo(function VelocityBlock() {
  const [vel, setVel] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchVel = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/news/velocity`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.ok) setVel(data.data);
    } catch { /* silent */ } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchVel();
    const iv = setInterval(fetchVel, 60000);
    return () => clearInterval(iv);
  }, [fetchVel]);

  if (loading && !vel) return null;
  if (!vel) return null;

  const lv = VELOCITY_LEVELS[vel.level] || VELOCITY_LEVELS.CALM;

  return (
    <div className="bg-white rounded-2xl border p-5" style={{ borderColor: c.border }}>
      <SectionHeader
        title="Скорость потока"
        tooltip="Анализ скорости поступления новостей: baseline (среднее за 24ч), ratio (текущее/среднее), тренд"
      />
      {/* Level badge */}
      <div
        data-testid="velocity-admin-block"
        className="p-4 rounded-xl mb-4 flex items-center justify-between"
        style={{ backgroundColor: lv.bg }}
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${lv.color}18` }}>
            <Gauge size={18} style={{ color: lv.color }} />
          </div>
          <div>
            <p className="text-sm font-bold" style={{ color: lv.color }}>{lv.label}</p>
            <p className="text-xs" style={{ color: `${lv.color}bb` }}>
              {vel.current ?? 0} сейчас · {vel.baseline ?? '—'} сред/ч · Ratio {vel.velocityRatio ?? '—'}x
            </p>
          </div>
        </div>
        {vel.trend24hPct !== undefined && vel.trend24hPct !== 0 && (
          <span className="text-xs font-medium px-2 py-1 rounded-lg" style={{
            backgroundColor: vel.trend24hPct > 0 ? c.successSoft : c.dangerSoft,
            color: vel.trend24hPct > 0 ? c.success : c.danger,
          }}>
            24ч: {vel.trend24hPct > 0 ? '+' : ''}{vel.trend24hPct}%
          </span>
        )}
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-4 gap-3">
        <div className="p-3 rounded-xl" style={{ backgroundColor: c.surface }}>
          <p className="text-xs mb-1" style={{ color: c.textMuted }}>За 1ч</p>
          <p className="text-xl font-bold" style={{ color: c.text }}>{vel.current ?? 0}</p>
          <p className="text-[10px]" style={{ color: c.textMuted }}>кластеров</p>
        </div>
        <div className="p-3 rounded-xl" style={{ backgroundColor: c.surface }}>
          <p className="text-xs mb-1" style={{ color: c.textMuted }}>Baseline</p>
          <p className="text-xl font-bold" style={{ color: c.text }}>{vel.baseline ?? '—'}</p>
          <p className="text-[10px]" style={{ color: c.textMuted }}>сред/час (24ч)</p>
        </div>
        <div className="p-3 rounded-xl" style={{ backgroundColor: c.surface }}>
          <p className="text-xs mb-1" style={{ color: c.textMuted }}>Рост vs среднего</p>
          <p className="text-xl font-bold" style={{
            color: (vel.growthPct ?? 0) > 0 ? c.success : (vel.growthPct ?? 0) < 0 ? c.danger : c.text
          }}>
            {vel.growthPct !== undefined ? `${vel.growthPct > 0 ? '+' : ''}${vel.growthPct}%` : '—'}
          </p>
          <p className="text-[10px]" style={{ color: c.textMuted }}>vs baseline</p>
        </div>
        <div className="p-3 rounded-xl" style={{ backgroundColor: c.surface }}>
          <p className="text-xs mb-1" style={{ color: c.textMuted }}>За 24ч</p>
          <p className="text-xl font-bold" style={{ color: c.text }}>{vel.clusters24h ?? 0}</p>
          <p className="text-[10px]" style={{ color: c.textMuted }}>
            вчера: {vel.clustersYesterday ?? 0}
          </p>
        </div>
      </div>

      {/* Breaking + High imp row */}
      {((vel.breakingLast1h ?? 0) > 0 || (vel.highImportanceLast1h ?? 0) > 0) && (
        <div className="flex gap-3 mt-3">
          {(vel.breakingLast1h ?? 0) > 0 && (
            <span className="text-xs px-2 py-1 rounded-lg font-medium"
              style={{ backgroundColor: c.dangerSoft, color: c.danger }}>
              {vel.breakingLast1h} breaking за 1ч
            </span>
          )}
          {(vel.highImportanceLast1h ?? 0) > 0 && (
            <span className="text-xs px-2 py-1 rounded-lg font-medium"
              style={{ backgroundColor: c.warningSoft, color: c.warning }}>
              {vel.highImportanceLast1h} high importance за 1ч
            </span>
          )}
        </div>
      )}
    </div>
  );
});

// ═══════════════════════════════════════════════════════════════
// OVERVIEW TAB
// ═══════════════════════════════════════════════════════════════
const OverviewTab = memo(function OverviewTab({ health, sources, loading, onRefresh, onRunParser }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin" style={{ color: c.accent }} />
      </div>
    );
  }

  const h = health || {};
  const sourcesData = sources?.sources || [];

  return (
    <div className="space-y-6">
      {/* Engine Status */}
      <div>
        <SectionHeader
          title="Статус движка"
          tooltip="Состояние новостного парсера и пайплайна обработки"
          action={
            <div className="flex items-center gap-2">
              <button
                data-testid="refresh-health-btn"
                onClick={onRefresh}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors"
                style={{ backgroundColor: c.surface, color: c.textSecondary }}
              >
                <RefreshCw size={14} />
                Обновить
              </button>
              <span className="flex items-center gap-1.5 text-sm" style={{ color: c.success }}>
                <CheckCircle size={14} />
                Движок готов
              </span>
            </div>
          }
        />

        <div className="grid grid-cols-3 gap-4">
          <div
            data-testid="engine-status-card"
            className="p-5 rounded-2xl"
            style={{ backgroundColor: h.activeSources > 0 ? '#ecfdf5' : c.dangerSoft }}
          >
            <p className="text-sm mb-1" style={{ color: c.textMuted }}>Статус</p>
            <p className="text-2xl font-bold" style={{ color: h.activeSources > 0 ? c.success : c.danger }}>
              {h.activeSources > 0 ? 'READY' : 'DOWN'}
            </p>
          </div>
          <div className="p-5 rounded-2xl" style={{ backgroundColor: c.surface }}>
            <p className="text-sm mb-1" style={{ color: c.textMuted }}>Uptime</p>
            <p className="text-2xl font-bold" style={{ color: c.text }}>
              {h.lastRunAt ? timeAgo(h.lastRunAt) : '—'}
            </p>
          </div>
          <div className="p-5 rounded-2xl" style={{ backgroundColor: c.surface }}>
            <p className="text-sm mb-1" style={{ color: c.textMuted }}>Дедупликация</p>
            <p className="text-2xl font-bold" style={{ color: c.text }}>
              {h.dedupeRate != null ? `${Math.round(h.dedupeRate * 100)}%` : '—'}
            </p>
            <p className="text-xs" style={{ color: c.textMuted }}>
              повторных отсеяно
            </p>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl border p-5" style={{ borderColor: c.border }}>
          <div className="flex items-center gap-2 mb-3">
            <Rss size={18} style={{ color: c.accent }} />
            <span className="text-sm font-medium" style={{ color: c.textSecondary }}>Источники</span>
          </div>
          <p className="text-3xl font-bold" style={{ color: c.text }}>{h.totalSources || 0}</p>
          <p className="text-xs mt-1" style={{ color: c.success }}>
            {h.activeSources || 0} активных
          </p>
        </div>
        <div className="bg-white rounded-2xl border p-5" style={{ borderColor: c.border }}>
          <div className="flex items-center gap-2 mb-3">
            <Newspaper size={18} style={{ color: '#06b6d4' }} />
            <span className="text-sm font-medium" style={{ color: c.textSecondary }}>За 1ч</span>
          </div>
          <p className="text-3xl font-bold" style={{ color: c.text }}>{h.eventsLast1h || 0}</p>
          <p className="text-xs mt-1" style={{ color: c.textMuted }}>новых событий</p>
        </div>
        <div className="bg-white rounded-2xl border p-5" style={{ borderColor: c.border }}>
          <div className="flex items-center gap-2 mb-3">
            <BarChart2 size={18} style={{ color: '#8b5cf6' }} />
            <span className="text-sm font-medium" style={{ color: c.textSecondary }}>За 24ч</span>
          </div>
          <p className="text-3xl font-bold" style={{ color: c.text }}>{h.eventsLast24h || 0}</p>
          <p className="text-xs mt-1" style={{ color: c.textMuted }}>
            6ч: {h.eventsLast6h || 0}
          </p>
        </div>
        <div className="bg-white rounded-2xl border p-5" style={{ borderColor: c.border }}>
          <div className="flex items-center gap-2 mb-3">
            <Zap size={18} style={{ color: '#f59e0b' }} />
            <span className="text-sm font-medium" style={{ color: c.textSecondary }}>Латентность</span>
          </div>
          <p className="text-3xl font-bold" style={{ color: c.text }}>
            {h.avgLatencyMs ? `${(h.avgLatencyMs / 1000).toFixed(1)}s` : '—'}
          </p>
          <p className="text-xs mt-1" style={{ color: c.textMuted }}>среднее время</p>
        </div>
      </div>

      {/* Velocity Block */}
      <VelocityBlock />

      {/* Top Sources */}
      {h.topSources?.length > 0 && (
        <div className="bg-white rounded-2xl border p-5" style={{ borderColor: c.border }}>
          <SectionHeader title="Топ источники" tooltip="Источники с наибольшим количеством статей" />
          <div className="space-y-3">
            {h.topSources.slice(0, 6).map((src, i) => {
              const tc = tierColors[src.tier] || tierColors.C;
              const maxArticles = h.topSources[0]?.articles || 1;
              return (
                <div key={src.name || i} className="flex items-center gap-3">
                  <span
                    className="w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs"
                    style={{ backgroundColor: tc.bg, color: tc.text }}
                  >
                    {src.tier}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium" style={{ color: c.text }}>{src.name}</span>
                      <span className="text-sm font-bold" style={{ color: c.text }}>{src.articles}</span>
                    </div>
                    <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: c.surface }}>
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${(src.articles / maxArticles) * 100}%`,
                          backgroundColor: tc.text
                        }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Quick Sources Status */}
      <div className="bg-white rounded-2xl border p-5" style={{ borderColor: c.border }}>
        <SectionHeader title="Источники" tooltip="Быстрый обзор состояния парсеров" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {sourcesData.map(src => {
            const tc = tierColors[src.tier] || tierColors.C;
            return (
              <div
                key={src.id}
                data-testid={`source-quick-${src.id}`}
                className="p-3 rounded-xl border transition-all hover:shadow-md"
                style={{ borderColor: src.healthy ? c.border : c.danger + '40' }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-sm" style={{ color: c.text }}>{src.name}</span>
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: src.healthy ? c.success : c.danger }}
                  />
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className="px-1.5 py-0.5 rounded text-[10px] font-bold"
                    style={{ backgroundColor: tc.bg, color: tc.text }}
                  >
                    {src.tier}
                  </span>
                  <span className="text-xs" style={{ color: c.textMuted }}>
                    {src.totalArticles} статей
                  </span>
                </div>
                <div className="text-[10px] mt-1" style={{ color: c.textMuted }}>
                  {timeAgo(src.lastFetchAt)}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
});

// ═══════════════════════════════════════════════════════════════
// SOURCES TAB
// ═══════════════════════════════════════════════════════════════
const SourcesTab = memo(function SourcesTab({ sources, loading, onRefresh }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [tierFilter, setTierFilter] = useState(null);

  const allSources = sources?.sources || [];
  const filtered = allSources.filter(src => {
    if (tierFilter && src.tier !== tierFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      if (!src.name?.toLowerCase().includes(q) && !src.id?.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries(tierColors).map(([tier, config]) => {
          const count = allSources.filter(s => s.tier === tier).length;
          return (
            <div
              key={tier}
              data-testid={`tier-${tier}-card`}
              className="p-5 rounded-2xl border cursor-pointer transition-all hover:shadow-lg"
              style={{
                backgroundColor: tierFilter === tier ? config.bg : 'white',
                borderColor: tierFilter === tier ? config.text : c.border
              }}
              onClick={() => setTierFilter(tierFilter === tier ? null : tier)}
            >
              <div className="flex items-center justify-between mb-2">
                <span
                  className="w-10 h-10 rounded-xl flex items-center justify-center font-bold text-lg"
                  style={{ backgroundColor: config.bg, color: config.text }}
                >
                  {tier}
                </span>
                <span className="text-3xl font-bold" style={{ color: config.text }}>{count}</span>
              </div>
              <p className="text-sm font-medium" style={{ color: c.text }}>Тир {tier}</p>
              <p className="text-xs" style={{ color: c.textSecondary }}>{config.label}</p>
            </div>
          );
        })}
        <div className="p-5 rounded-2xl border" style={{ borderColor: c.border }}>
          <div className="flex items-center justify-between mb-2">
            <span
              className="w-10 h-10 rounded-xl flex items-center justify-center font-bold text-lg"
              style={{ backgroundColor: c.surface, color: c.accent }}
            >
              <Globe size={20} />
            </span>
            <span className="text-3xl font-bold" style={{ color: c.accent }}>{allSources.length}</span>
          </div>
          <p className="text-sm font-medium" style={{ color: c.text }}>Всего</p>
          <p className="text-xs" style={{ color: c.textSecondary }}>источников</p>
        </div>
      </div>

      {/* Search */}
      <div className="bg-white rounded-2xl border p-4" style={{ borderColor: c.border }}>
        <div className="relative">
          <Search size={20} className="absolute left-4 top-1/2 -translate-y-1/2" style={{ color: c.textMuted }} />
          <input
            data-testid="sources-search-input"
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Поиск по названию или ID..."
            className="w-full pl-12 pr-12 py-3 rounded-xl border transition-all focus:outline-none focus:ring-2 focus:ring-indigo-200"
            style={{ borderColor: c.border, backgroundColor: c.surface, color: c.text }}
          />
          {searchQuery && (
            <button onClick={() => setSearchQuery('')} className="absolute right-4 top-1/2 -translate-y-1/2">
              <X size={16} style={{ color: c.textMuted }} />
            </button>
          )}
        </div>
      </div>

      {/* Active Filters */}
      {tierFilter && (
        <div className="flex items-center gap-2">
          <span className="text-sm" style={{ color: c.textSecondary }}>Фильтр:</span>
          <button
            onClick={() => setTierFilter(null)}
            className="px-3 py-1 rounded-full text-sm flex items-center gap-1"
            style={{ backgroundColor: tierColors[tierFilter]?.bg, color: tierColors[tierFilter]?.text }}
          >
            Тир {tierFilter} <X size={14} />
          </button>
        </div>
      )}

      {/* Sources Table */}
      <div className="bg-white rounded-2xl border overflow-hidden" style={{ borderColor: c.border }}>
        <table className="w-full">
          <thead>
            <tr style={{ backgroundColor: c.surface }}>
              <th className="px-6 py-4 text-left text-sm font-medium" style={{ color: c.textSecondary }}>Источник</th>
              <th className="px-6 py-4 text-left text-sm font-medium" style={{ color: c.textSecondary }}>Тир</th>
              <th className="px-6 py-4 text-left text-sm font-medium" style={{ color: c.textSecondary }}>Язык</th>
              <th className="px-6 py-4 text-right text-sm font-medium" style={{ color: c.textSecondary }}>Статей</th>
              <th className="px-6 py-4 text-right text-sm font-medium" style={{ color: c.textSecondary }}>Успешность</th>
              <th className="px-6 py-4 text-left text-sm font-medium" style={{ color: c.textSecondary }}>Статус</th>
              <th className="px-6 py-4 text-left text-sm font-medium" style={{ color: c.textSecondary }}>Последний</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-12 text-center" style={{ color: c.textMuted }}>
                  Источники не найдены
                </td>
              </tr>
            ) : (
              filtered.map((src, idx) => {
                const tc = tierColors[src.tier] || tierColors.C;
                return (
                  <tr
                    key={src.id || idx}
                    data-testid={`source-row-${src.id}`}
                    className="border-t transition-colors hover:bg-gray-50"
                    style={{ borderColor: c.border }}
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: c.accentSoft }}>
                          <Rss size={18} style={{ color: c.accent }} />
                        </div>
                        <div>
                          <p className="font-medium" style={{ color: c.text }}>{src.name}</p>
                          <p className="text-xs" style={{ color: c.textMuted }}>{src.id}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-3 py-1 rounded-lg font-bold text-sm" style={{ backgroundColor: tc.bg, color: tc.text }}>
                        {src.tier}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm uppercase" style={{ color: c.text }}>
                        {src.lang === 'en' ? '🇬🇧' : '🇷🇺'} {src.lang || 'en'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span className="font-bold" style={{ color: c.text }}>{src.totalArticles || 0}</span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span
                        className="font-medium"
                        style={{ color: (src.successRate || 0) >= 0.9 ? c.success : (src.successRate || 0) >= 0.7 ? c.warning : c.danger }}
                      >
                        {src.successRate != null ? `${Math.round(src.successRate * 100)}%` : '—'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {src.healthy ? (
                        <span className="flex items-center gap-1 text-sm" style={{ color: c.success }}>
                          <CheckCircle size={14} /> Активен
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-sm" style={{ color: c.danger }}>
                          <XCircle size={14} /> Ошибка
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-xs" style={{ color: c.textMuted }}>
                        {timeAgo(src.lastFetchAt)}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
});

// ═══════════════════════════════════════════════════════════════
// HEALTH TAB
// ═══════════════════════════════════════════════════════════════
const HealthTab = memo(function HealthTab({ health, sources, loading, onRefresh }) {
  const allSources = sources?.sources || [];
  const h = health || {};

  return (
    <div className="space-y-6">
      {/* Pipeline Health */}
      <div className="bg-white rounded-2xl border p-6" style={{ borderColor: c.border }}>
        <SectionHeader
          title="Здоровье пайплайна"
          tooltip="Мониторинг работоспособности всех компонентов новостного пайплайна"
          action={
            <button
              data-testid="refresh-pipeline-btn"
              onClick={onRefresh}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm"
              style={{ backgroundColor: c.surface, color: c.textSecondary }}
            >
              <RefreshCw size={14} /> Обновить
            </button>
          }
        />

        <div className="grid grid-cols-5 gap-4 mb-6">
          <div className="text-center p-4 rounded-xl" style={{ backgroundColor: c.successSoft }}>
            <p className="text-2xl font-bold" style={{ color: c.success }}>{h.healthySources || 0}</p>
            <p className="text-xs" style={{ color: c.textSecondary }}>Здоровых</p>
          </div>
          <div className="text-center p-4 rounded-xl" style={{ backgroundColor: h.unhealthySources > 0 ? c.dangerSoft : c.surface }}>
            <p className="text-2xl font-bold" style={{ color: h.unhealthySources > 0 ? c.danger : c.textMuted }}>
              {h.unhealthySources || 0}
            </p>
            <p className="text-xs" style={{ color: c.textSecondary }}>С ошибками</p>
          </div>
          <div className="text-center p-4 rounded-xl" style={{ backgroundColor: c.surface }}>
            <p className="text-2xl font-bold" style={{ color: c.text }}>
              {h.errorRate != null ? `${Math.round(h.errorRate * 100)}%` : '0%'}
            </p>
            <p className="text-xs" style={{ color: c.textSecondary }}>Ошибок</p>
          </div>
          <div className="text-center p-4 rounded-xl" style={{ backgroundColor: c.surface }}>
            <p className="text-2xl font-bold" style={{ color: c.text }}>
              {h.avgLatencyMs ? `${(h.avgLatencyMs / 1000).toFixed(1)}s` : '—'}
            </p>
            <p className="text-xs" style={{ color: c.textSecondary }}>Латентность</p>
          </div>
          <div className="text-center p-4 rounded-xl" style={{ backgroundColor: c.surface }}>
            <p className="text-2xl font-bold" style={{ color: c.text }}>
              {h.dedupeRate != null ? `${Math.round(h.dedupeRate * 100)}%` : '—'}
            </p>
            <p className="text-xs" style={{ color: c.textSecondary }}>Дедупликация</p>
          </div>
        </div>

        {/* Per-Source Health */}
        <div className="space-y-2">
          {allSources.map(src => {
            const rate = src.successRate || 0;
            return (
              <div
                key={src.id}
                data-testid={`health-source-${src.id}`}
                className="flex items-center justify-between p-3 rounded-xl transition-all"
                style={{ backgroundColor: c.surface }}
              >
                <div className="flex items-center gap-3">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: src.healthy ? c.success : c.danger }}
                  />
                  <span className="font-medium text-sm" style={{ color: c.text }}>{src.name}</span>
                  <span
                    className="px-1.5 py-0.5 rounded text-[10px] font-bold"
                    style={{ backgroundColor: tierColors[src.tier]?.bg, color: tierColors[src.tier]?.text }}
                  >
                    {src.tier}
                  </span>
                  {src.consecutiveFailures > 0 && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold" style={{ backgroundColor: c.dangerSoft, color: c.danger }}>
                      {src.consecutiveFailures} ошибок подряд
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-4 text-xs" style={{ color: c.textMuted }}>
                  <div className="text-right">
                    <div className="font-medium" style={{ color: rate >= 0.9 ? c.success : rate >= 0.7 ? c.warning : c.danger }}>
                      {Math.round(rate * 100)}%
                    </div>
                    <div>успешных</div>
                  </div>
                  <div className="w-20">
                    <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: c.border }}>
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${rate * 100}%`,
                          backgroundColor: rate >= 0.9 ? c.success : rate >= 0.7 ? c.warning : c.danger
                        }}
                      />
                    </div>
                  </div>
                  <div className="text-right w-20">
                    <div className="font-medium" style={{ color: c.text }}>{src.totalFetches || 0}</div>
                    <div>запросов</div>
                  </div>
                  <div className="text-right w-24">
                    <div>{timeAgo(src.lastFetchAt)}</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Last Error */}
      {allSources.some(s => s.lastError) && (
        <div className="bg-white rounded-2xl border p-6" style={{ borderColor: c.border }}>
          <SectionHeader title="Последние ошибки" tooltip="Ошибки из последних запросов к источникам" />
          <div className="space-y-2">
            {allSources.filter(s => s.lastError).map(src => (
              <div
                key={src.id}
                className="p-3 rounded-xl flex items-center gap-3"
                style={{ backgroundColor: c.dangerSoft }}
              >
                <AlertTriangle size={16} style={{ color: c.danger }} />
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium" style={{ color: c.text }}>{src.name}</span>
                  <p className="text-xs truncate" style={{ color: c.textSecondary }}>{src.lastError}</p>
                </div>
                <span className="text-xs flex-shrink-0" style={{ color: c.textMuted }}>
                  {timeAgo(src.lastErrorAt)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});

// ═══════════════════════════════════════════════════════════════
// EVENTS TAB
// ═══════════════════════════════════════════════════════════════
const EventsTab = memo(function EventsTab({ loading }) {
  const [events, setEvents] = useState([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [limit, setLimit] = useState(20);

  const fetchEvents = useCallback(async () => {
    setEventsLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/news/events?limit=${limit}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setEvents(data.ok ? (data.data?.events || []) : []);
    } catch (err) {
      console.error('Failed to fetch events:', err);
    }
    setEventsLoading(false);
  }, [limit]);

  useEffect(() => { fetchEvents(); }, [fetchEvents]);

  const eventTypeConfig = {
    regulation: { bg: '#fef3c7', color: '#d97706' },
    funding: { bg: '#d1fae5', color: '#059669' },
    price: { bg: '#dbeafe', color: '#2563eb' },
    macro: { bg: '#e0e7ff', color: '#4f46e5' },
    hack: { bg: '#fee2e2', color: '#dc2626' },
    launch: { bg: '#ede9fe', color: '#7c3aed' },
    partnership: { bg: '#fce7f3', color: '#db2777' },
    etf: { bg: '#d1fae5', color: '#059669' },
    market: { bg: '#f3f4f6', color: '#374151' },
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <SectionHeader title="Последние события" tooltip="Необработанные события из RSS-парсера" />
        <div className="flex items-center gap-2">
          <select
            data-testid="events-limit-select"
            value={limit}
            onChange={e => setLimit(Number(e.target.value))}
            className="px-3 py-1.5 rounded-lg border text-sm"
            style={{ borderColor: c.border, color: c.text }}
          >
            <option value={10}>10</option>
            <option value={20}>20</option>
            <option value={50}>50</option>
          </select>
          <button
            data-testid="refresh-events-btn"
            onClick={fetchEvents}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm"
            style={{ backgroundColor: c.surface, color: c.textSecondary }}
          >
            <RefreshCw size={14} /> Обновить
          </button>
        </div>
      </div>

      {eventsLoading ? (
        <div className="flex items-center justify-center h-32">
          <Loader2 className="w-6 h-6 animate-spin" style={{ color: c.accent }} />
        </div>
      ) : events.length === 0 ? (
        <div className="bg-white rounded-2xl border p-12 text-center" style={{ borderColor: c.border }}>
          <FileText size={48} className="mx-auto mb-4" style={{ color: c.textMuted }} />
          <p className="font-medium" style={{ color: c.text }}>Нет событий</p>
        </div>
      ) : (
        <div className="space-y-3">
          {events.map((ev, idx) => {
            const evType = ev.raw?.feedTier ? 'news' : 'unknown';
            // Handle categories that can be strings or objects (CoinDesk returns {_: "Finance", $: {...}})
            const firstCat = ev.raw?.categories?.[0];
            const catStr = typeof firstCat === 'string' ? firstCat : (firstCat?._ || firstCat?.name || '');
            const tc = eventTypeConfig[catStr?.toLowerCase?.()] || { bg: c.surface, color: c.textMuted };
            return (
              <div
                key={ev.externalId || idx}
                data-testid={`event-${idx}`}
                className="bg-white rounded-2xl border p-4 transition-all hover:shadow-md"
                style={{ borderColor: c.border }}
              >
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ backgroundColor: c.accentSoft }}>
                    <Newspaper size={18} style={{ color: c.accent }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm mb-1" style={{ color: c.text }}>{ev.title}</p>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs" style={{ color: c.textMuted }}>
                        {ev.publisher?.name || ev.sourceName}
                      </span>
                      {ev.assetMentions?.map(a => (
                        <span key={a} className="px-1.5 py-0.5 rounded text-[10px] font-bold" style={{ backgroundColor: '#dbeafe', color: '#2563eb' }}>
                          {a}
                        </span>
                      ))}
                      {ev.raw?.categories?.slice(0, 3).map((cat, catIdx) => {
                        // Handle both string and object categories
                        const catLabel = typeof cat === 'string' ? cat : (cat?._ || cat?.name || JSON.stringify(cat));
                        return (
                          <span key={catIdx} className="px-1.5 py-0.5 rounded text-[10px]" style={{ backgroundColor: c.surface, color: c.textSecondary }}>
                            {catLabel}
                          </span>
                        );
                      })}
                      <span className="flex items-center gap-1 text-xs" style={{ color: c.textMuted }}>
                        <Clock size={10} /> {timeAgo(ev.publishedAt)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
});

// ═══════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════
export default function NewsAdminPage() {
  // Tab from URL
  const params = new URLSearchParams(window.location.search);
  const initialTab = params.get('tab') || 'overview';
  const [activeTab, setActiveTab] = useState(initialTab);

  // Data
  const [health, setHealth] = useState(null);
  const [sources, setSources] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [healthRes, sourcesRes] = await Promise.all([
        fetch(`${API_URL}/api/admin/news/health`),
        fetch(`${API_URL}/api/admin/news/sources`),
      ]);
      const [healthData, sourcesData] = await Promise.all([healthRes.json(), sourcesRes.json()]);
      setHealth(healthData.ok ? healthData.data : null);
      setSources(sourcesData.ok ? sourcesData.data : null);
    } catch (err) {
      console.error('Failed to fetch admin data:', err);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Auto-refresh
  useEffect(() => {
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    const url = new URL(window.location);
    if (tab === 'overview') {
      url.searchParams.delete('tab');
    } else {
      url.searchParams.set('tab', tab);
    }
    window.history.replaceState({}, '', url);
  };

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6" data-testid="news-admin-page">
        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold flex items-center gap-3" style={{ color: c.text }}>
            <Rss size={28} style={{ color: c.accent }} />
            News Parser
          </h1>
          <p className="text-sm mt-1" style={{ color: c.textSecondary }}>
            Управление новостным парсером и источниками данных
          </p>
        </div>

        {/* Sub-Tab Navigation */}
        <div className="flex gap-1 mb-8 p-1 rounded-xl" style={{ backgroundColor: c.surface }}>
          {TABS.map(tab => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                data-testid={`tab-${tab.id}`}
                onClick={() => handleTabChange(tab.id)}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all"
                style={{
                  backgroundColor: isActive ? 'white' : 'transparent',
                  color: isActive ? c.accent : c.textSecondary,
                  boxShadow: isActive ? '0 1px 3px rgba(0,0,0,0.1)' : 'none'
                }}
              >
                <Icon size={16} />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <OverviewTab
            health={health}
            sources={sources}
            loading={loading}
            onRefresh={fetchAll}
          />
        )}
        {activeTab === 'sources' && (
          <SourcesTab
            sources={sources}
            loading={loading}
            onRefresh={fetchAll}
          />
        )}
        {activeTab === 'health' && (
          <HealthTab
            health={health}
            sources={sources}
            loading={loading}
            onRefresh={fetchAll}
          />
        )}
        {activeTab === 'events' && (
          <EventsTab loading={loading} />
        )}
      </div>
    </AdminLayout>
  );
}
