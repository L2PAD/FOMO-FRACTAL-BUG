/**
 * Shadow Gate panel — PHASE 2 / I1 / R8
 * Sources: /api/ta-prediction-intelligence/shadow-gate/stats + /recent
 * STRICTLY NO buttons. Read-only.
 *
 * 2026-05-08 cleanup:
 *   • font-mono убран — используется глобальный Gilroy.
 *   • UPPER_SNAKE-коды (INTEGRITY_UNRELIABLE / NO_EDGE) проходят через humanize().
 *   • Длинные prediction_id (tap-1425e02ae8634362) показываются как
 *     `tap-1425…4362`, полный ID — в title-tooltip.
 *   • Заголовки колонок таблицы — на русском.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Card, CardContent } from '../../ui/card';
import {
  fetchShadowGateStats,
  fetchShadowGateRecent,
} from '../../../services/taPredictionApi';
import {
  ReadOnlyHeader,
  PanelStateBlock,
  EpistemicBanner,
  StateBadge,
  fmtPct,
  fmtTime,
  humanize,
  shortId,
} from './primitives';

function Stat({ label, value, sub, state }) {
  return (
    <div className="rounded-md border border-gray-200 bg-gray-50 p-3">
      <div className="text-[11px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className="text-2xl font-semibold text-gray-900">{value}</div>
      <div className="flex items-center justify-between mt-1">
        <span className="text-xs text-gray-500">{sub || '\u00a0'}</span>
        {state && <StateBadge state={state} />}
      </div>
    </div>
  );
}

export default function ShadowGatePanel() {
  const [stats, setStats] = useState(null);
  const [recent, setRecent] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [s, r] = await Promise.all([
        fetchShadowGateStats(),
        fetchShadowGateRecent(20),
      ]);
      setStats(s);
      setRecent(r);
    } catch (e) {
      setError(e);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    let mounted = true;
    refetch();
    return () => { mounted = false; };
  }, [refetch]);

  let state;
  if (loading && !stats) state = 'loading';
  else if (error) state = 'error';
  else if (!stats) state = 'unavailable';
  else if (stats.total === 0) state = 'empty_sample';
  else state = 'healthy';

  const allowedRate = stats && stats.total > 0 ? stats.allowed / stats.total : null;
  const blockedRate = stats && stats.total > 0 ? stats.blocked / stats.total : null;
  const sortedReasons = stats ? Object.entries(stats.reason_histogram).sort((a, b) => b[1] - a[1]) : [];

  return (
    <div className="p-6 space-y-4" data-testid="observability-shadow-gate">
      <ReadOnlyHeader
        title="Shadow Gate"
        subtitle="Вердикты shadow-gate · allowed / blocked · топ причин блокировок"
        endpoint="GET /api/ta-prediction-intelligence/shadow-gate/stats + /recent"
        state={state}
        onRefresh={() => refetch()}
        loading={loading}
      />
      <Card>
        <CardContent className="p-4 space-y-4">
          {state === 'loading' || state === 'error' || state === 'unavailable' ? (
            <PanelStateBlock
              state={state}
              message={state === 'error' ? (error instanceof Error ? error.message : 'Сетевая или backend-ошибка.') : undefined}
            />
          ) : state === 'empty_sample' ? (
            <EpistemicBanner severity="info" title="Пока нет вердиктов shadow-gate">
              Shadow-gate ещё не оценил ни одного прогноза в текущем окне.
            </EpistemicBanner>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-3">
                <Stat label="Всего" value={String(stats.total)} />
                <Stat label="Allowed" value={`${stats.allowed}`} sub={fmtPct(allowedRate)} state="healthy" />
                <Stat label="Blocked" value={`${stats.blocked}`} sub={fmtPct(blockedRate)} state={stats.blocked > 0 ? 'degraded' : 'healthy'} />
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-2">Топ причин блокировок</div>
                {sortedReasons.length === 0 ? (
                  <div className="text-xs text-gray-500">Причин блокировок пока нет.</div>
                ) : (
                  <div className="space-y-1.5">
                    {sortedReasons.map(([reason, count]) => {
                      const pct = stats.total > 0 ? count / stats.total : 0;
                      return (
                        <div key={reason} className="flex items-center gap-3 text-sm">
                          <span
                            className="text-gray-700 w-56 truncate text-xs"
                            title={reason}
                          >
                            {humanize(reason)}
                          </span>
                          <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                            <div className="h-full bg-amber-500 transition-all" style={{ width: `${Math.min(100, pct * 100)}%` }} />
                          </div>
                          <span className="w-20 text-right text-xs text-gray-700 tabular-nums">
                            {count} · {fmtPct(pct)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-2">
                  Последние вердикты ({recent?.count ?? 0})
                </div>
                {!recent || recent.items.length === 0 ? (
                  <div className="text-xs text-gray-500">Свежих вердиктов нет.</div>
                ) : (
                  <div className="overflow-x-auto rounded-md border border-gray-200">
                    <table className="w-full text-xs">
                      <thead className="bg-gray-50 text-gray-600">
                        <tr>
                          <th className="text-left px-3 py-2 font-medium">Время</th>
                          <th className="text-left px-3 py-2 font-medium">Символ · TF</th>
                          <th className="text-left px-3 py-2 font-medium">Вердикт</th>
                          <th className="text-left px-3 py-2 font-medium">Целостность</th>
                          <th className="text-left px-3 py-2 font-medium">Сигнал</th>
                          <th className="text-left px-3 py-2 font-medium">Причины</th>
                          <th className="text-left px-3 py-2 font-medium">ID прогноза</th>
                        </tr>
                      </thead>
                      <tbody>
                        {recent.items.map(it => (
                          <tr key={it.prediction_id} className="border-t border-gray-100">
                            <td className="px-3 py-2 text-gray-700 whitespace-nowrap tabular-nums">
                              {fmtTime(it.evaluated_at)}
                            </td>
                            <td className="px-3 py-2 text-gray-700 whitespace-nowrap">
                              {it.symbol} · {it.timeframe}
                            </td>
                            <td className="px-3 py-2">
                              <StateBadge
                                state={it.would_allow_prediction ? 'healthy' : 'degraded'}
                                override={it.would_allow_prediction ? 'allow' : 'block'}
                              />
                            </td>
                            <td className="px-3 py-2 text-gray-700">{humanize(it.integrity_status)}</td>
                            <td className="px-3 py-2 text-gray-700">{humanize(it.signal_strength)}</td>
                            <td className="px-3 py-2 text-gray-700">
                              {it.block_reasons?.length
                                ? it.block_reasons.map(r => humanize(r)).join(', ')
                                : '—'}
                            </td>
                            <td
                              className="px-3 py-2 text-gray-500 whitespace-nowrap tabular-nums"
                              title={it.prediction_id}
                            >
                              {shortId(it.prediction_id)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
              <div className="text-[11px] text-gray-500 pt-2 border-t">
                Read-only. Shadow-gate работает в режиме <span className="font-medium text-gray-700">shadow-only</span> и не влияет на исполнение.
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
