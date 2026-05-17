/**
 * Admin observability shared primitives — PHASE 2 / I1.
 * Honest state ladder, severity coloring, epistemic banners.
 * Used by all 6 read-only TA-R5..R10 panels.
 *
 * 2026-05-08 cleanup:
 *   • All `font-mono` removed (Gilroy is global default).
 *   • `humanize()` and `shortId()` helpers added so admin doesn't show
 *     INTEGRITY_UNRELIABLE / NO_EDGE / tap-1425e02ae8634362 verbatim.
 *   • `ReadOnlyHeader.endpoint` is now a subtle inline note (no mono).
 */

import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  Loader2,
  Info,
  ShieldAlert,
  Shield,
  XCircle,
} from 'lucide-react';

// ─── State ladder — the only allowed states for observability surfaces ──
const STATE_META = {
  loading:      { cls: 'bg-gray-100 text-gray-600',         label: 'Загрузка',          icon: Loader2 },
  healthy:      { cls: 'bg-emerald-100 text-emerald-700',   label: 'Healthy',           icon: CheckCircle2 },
  degraded:     { cls: 'bg-amber-100 text-amber-700',       label: 'Degraded',          icon: AlertTriangle },
  unavailable:  { cls: 'bg-gray-100 text-gray-600',         label: 'Недоступно',        icon: ShieldAlert },
  empty_sample: { cls: 'bg-sky-100 text-sky-700',           label: 'Мало данных',       icon: Info },
  error:        { cls: 'bg-red-100 text-red-700',           label: 'Ошибка',            icon: XCircle },
};

export function StateBadge({ state, override }) {
  const meta = STATE_META[state] || STATE_META.unavailable;
  const Icon = meta.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium ${meta.cls}`}
      data-testid={`state-badge-${state}`}
    >
      <Icon
        className={`w-3.5 h-3.5 ${state === 'loading' ? 'animate-spin' : ''}`}
        strokeWidth={1.75}
      />
      {override || meta.label}
    </span>
  );
}

export function PanelStateBlock({ state, title, message }) {
  const meta = STATE_META[state] || STATE_META.unavailable;
  const Icon = meta.icon;
  const titleStr =
    title ||
    (state === 'loading'
      ? 'Загрузка…'
      : state === 'unavailable'
      ? 'Backend недоступен'
      : state === 'empty_sample'
      ? 'Недостаточно данных'
      : state === 'error'
      ? 'Ошибка получения данных'
      : meta.label);

  return (
    <div
      className="flex flex-col items-center justify-center py-12 text-center text-gray-600"
      data-testid={`panel-state-${state}`}
    >
      <Icon
        className={`w-7 h-7 mb-3 ${state === 'loading' ? 'animate-spin text-gray-400' : 'text-gray-400'}`}
        strokeWidth={1.5}
      />
      <div className="text-sm font-semibold text-gray-800">{titleStr}</div>
      {message && (
        <div className="text-xs text-gray-500 mt-1 max-w-md whitespace-pre-line">
          {message}
        </div>
      )}
    </div>
  );
}

const EPISTEMIC_META = {
  info:     { cls: 'bg-sky-50 border-sky-200 text-sky-800',          icon: Info },
  warning:  { cls: 'bg-amber-50 border-amber-200 text-amber-800',    icon: AlertTriangle },
  critical: { cls: 'bg-red-50 border-red-200 text-red-800',          icon: AlertOctagon },
};

export function EpistemicBanner({ severity, title, children }) {
  const meta = EPISTEMIC_META[severity] || EPISTEMIC_META.info;
  const Icon = meta.icon;
  return (
    <div
      className={`flex items-start gap-3 rounded-md border px-3 py-2 ${meta.cls}`}
      data-testid={`epistemic-banner-${severity}`}
      role="status"
    >
      <Icon className="w-4 h-4 mt-0.5 shrink-0" strokeWidth={1.75} />
      <div className="min-w-0">
        <div className="text-sm font-semibold">{title}</div>
        {children && <div className="text-xs mt-0.5 opacity-90">{children}</div>}
      </div>
    </div>
  );
}

export function ReadOnlyHeader({
  title,
  subtitle,
  state,
  endpoint, // kept for accessibility; rendered as a subtle tooltip-attr,
  // не как monospace-плашка под заголовком.
  onRefresh,
  loading,
  rightSlot,
}) {
  return (
    <div className="flex items-start justify-between gap-3 flex-wrap" title={endpoint || undefined}>
      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <Shield className="w-4 h-4 text-indigo-600" strokeWidth={1.75} />
          <h2 className="text-base font-semibold text-gray-900">{title}</h2>
          <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
            Read-only
          </span>
          {state && <StateBadge state={state} />}
        </div>
        {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-2">
        {rightSlot}
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            className="text-xs px-2.5 py-1 rounded-md border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-50"
            data-testid="observability-refresh"
          >
            {loading ? 'Обновляется…' : 'Обновить'}
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Reusable «pretty value» wrapper ──────────────────────────────
// Используется вместо <span className="font-mono"> для технических
// значений (числа / freeze label / regime key и т.п.). Шрифт — Gilroy
// (global default), цвет — gray-900, выравнивание по правому краю.
export function Value({ children, className = '', testid }) {
  return (
    <span
      className={`text-gray-900 break-words text-right ${className}`}
      data-testid={testid}
    >
      {children}
    </span>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────

export const fmtPct = (v, digits = 1) => {
  if (v === null || v === undefined) return '—';
  if (Number.isNaN(v)) return '—';
  return `${(v * 100).toFixed(digits)}%`;
};

export const fmtNum = (v, digits = 0) => {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return v.toFixed(digits);
};

export const fmtTime = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return iso;
  }
};

// Tokens that must stay UPPERCASE (or specific-cased) when humanizing.
// Включает индикаторы-аббревиатуры, которые читаются как код, а не слово.
const KEEP_TOKENS = new Set([
  'OK', 'ID', 'TF', 'ML', 'TA', 'API', 'MTF', 'PnL',
  'R1', 'R2', 'R5', 'R6', 'R7', 'R8', 'R9', 'R10',
  'BTC', 'BTCUSDT', 'ETH', 'ETHUSDT', 'USDT',
  'CORE7', 'RSI', 'MACD', 'EMA', 'SMA', 'ATR', 'ADX', 'OBV',
  'OHLCV', 'TP', 'SL',
]);

/**
 * Превращает строку-код вида `INTEGRITY_UNRELIABLE` или `gate_quality_good`
 * в человекочитаемое описание: `Integrity unreliable` / `Gate quality good`.
 *
 * Правила:
 *   • Разделители `_`, `-`, `.` → пробел.
 *   • Aббревиатуры из KEEP_TOKENS остаются в исходном регистре.
 *   • Первое слово — Capitalize, остальные — lowercase (sentence case).
 *
 * @param {string|null|undefined} code
 * @param {object} [opts]
 * @param {string} [opts.fallback='—']
 * @returns {string}
 */
export function humanize(code, { fallback = '—' } = {}) {
  if (code === null || code === undefined || code === '') return fallback;
  const raw = String(code);
  // If already looks like a normal phrase (has space, lowercase letters), pass through.
  if (/\s/.test(raw) && raw !== raw.toUpperCase()) return raw;

  const tokens = raw
    .split(/[_\-.]+/)
    .filter(Boolean)
    .map((tok, i) => {
      if (KEEP_TOKENS.has(tok)) return tok;
      const upper = tok.toUpperCase();
      if (KEEP_TOKENS.has(upper)) return upper;
      const lower = tok.toLowerCase();
      if (i === 0) return lower.charAt(0).toUpperCase() + lower.slice(1);
      return lower;
    });

  return tokens.join(' ');
}

/**
 * Сокращает длинный технический ID вида `tap-1425e02ae8634362` до
 * `tap-1425…4362` — оставляя префикс до первого `-` и хвост из 4 символов.
 * Полный ID доступен через title-attribute (тултип).
 *
 * @param {string|null|undefined} id
 * @param {object} [opts]
 * @param {number} [opts.head=4]   — сколько символов хвоста префикса показать
 * @param {number} [opts.tail=4]   — сколько символов хвоста payload показать
 * @returns {string}
 */
export function shortId(id, { head = 4, tail = 4 } = {}) {
  if (!id) return '—';
  const s = String(id);
  if (s.length <= head + tail + 4) return s;
  const dashIdx = s.indexOf('-');
  if (dashIdx > 0 && dashIdx < 8) {
    const prefix = s.slice(0, dashIdx);
    const payload = s.slice(dashIdx + 1);
    if (payload.length <= head + tail + 1) return s;
    return `${prefix}-${payload.slice(0, head)}…${payload.slice(-tail)}`;
  }
  return `${s.slice(0, head + 4)}…${s.slice(-tail)}`;
}
