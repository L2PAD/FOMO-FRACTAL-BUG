/**
 * Twitter Stability Monitor Tab
 * ==============================
 * Shows standby state, session breakdown, scheduler info.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../../../../components/ui/card';
import { RefreshCw, Loader2, Shield, Wifi, WifiOff, Clock, Activity, CheckCircle } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function TwitterStabilityTab() {
  const [standby, setStandby] = useState(null);
  const [scheduler, setScheduler] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [sRes, schRes] = await Promise.all([
        fetch(`${API_URL}/api/v4/admin/system/standby`).then(r => r.json()).catch(() => null),
        fetch(`${API_URL}/api/v4/admin/system/scheduler/status`).then(r => r.json()).catch(() => null),
      ]);
      if (sRes?.ok) setStandby(sRes.data);
      if (schRes?.ok) setScheduler(schRes.data);
    } catch (err) {
      console.error('[StabilityTab] fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const iv = setInterval(fetchAll, 30000);
    return () => clearInterval(iv);
  }, [fetchAll]);

  if (loading && !standby) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
        <span className="ml-2 text-sm text-slate-400">Загрузка...</span>
      </div>
    );
  }

  const stateLabel = standby?.state === 'ACTIVE' ? 'АКТИВЕН' : standby?.state === 'STANDBY' ? 'ОЖИДАНИЕ' : 'Неизвестно';
  const stateColor = standby?.state === 'ACTIVE' ? 'emerald' : standby?.state === 'STANDBY' ? 'amber' : 'gray';

  return (
    <div className="space-y-6" data-testid="twitter-stability-tab">
      {/* Refresh */}
      <div className="flex justify-end">
        <button
          onClick={fetchAll}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-slate-100 hover:bg-slate-200 rounded-lg text-slate-600 transition"
          data-testid="stability-refresh-btn"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Обновить
        </button>
      </div>

      {/* Main State Card */}
      <Card>
        <CardContent className="p-6">
          <div className="flex items-start gap-6">
            {/* State Indicator */}
            <div className={`flex-shrink-0 w-16 h-16 rounded-2xl flex items-center justify-center ${
              stateColor === 'emerald' ? 'bg-emerald-100' : stateColor === 'amber' ? 'bg-amber-100' : 'bg-gray-100'
            }`}>
              {standby?.state === 'ACTIVE' ? (
                <Wifi className={`w-7 h-7 text-emerald-600`} />
              ) : standby?.state === 'STANDBY' ? (
                <WifiOff className={`w-7 h-7 text-amber-600`} />
              ) : (
                <Shield className="w-7 h-7 text-gray-400" />
              )}
            </div>

            <div className="flex-1">
              <div className="flex items-center gap-3 mb-1">
                <span className={`text-2xl font-bold text-${stateColor}-700`}>
                  {stateLabel}
                </span>
                <span className={`w-3 h-3 rounded-full animate-pulse bg-${stateColor}-500`} />
              </div>
              
              {standby?.state === 'ACTIVE' && (
                <p className="text-sm text-slate-500">
                  Парсер работает в штатном режиме. {standby?.okSessions || 0} из {standby?.totalSessions || 0} сессий активны.
                </p>
              )}
              {standby?.state === 'STANDBY' && (
                <p className="text-sm text-amber-700">
                  Все cookies недействительны. Парсер в режиме ожидания — автоматически возобновит работу при обнаружении валидных сессий.
                </p>
              )}

              {standby?.stateChangedAt && (
                <p className="text-xs text-slate-400 mt-2">
                  Статус с: {new Date(standby.stateChangedAt).toLocaleString()}
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Session Breakdown */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Всего сессий', value: standby?.totalSessions || 0, color: 'slate' },
          { label: 'Активные (OK)', value: standby?.okSessions || 0, color: 'emerald' },
          { label: 'Устаревшие (STALE)', value: standby?.staleSessions || 0, color: 'amber' },
          { label: 'Истёкшие', value: standby?.expiredSessions || 0, color: 'red' },
        ].map(({ label, value, color }) => (
          <Card key={label}>
            <CardContent className="p-4">
              <p className="text-xs text-slate-500 mb-1">{label}</p>
              <p className={`text-2xl font-bold text-${color}-600`}>{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Scheduler Info */}
      {scheduler && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Clock className="w-4 h-4 text-indigo-500" />
              Планировщик парсинга
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-slate-500">Статус</p>
                <p className={`font-semibold ${scheduler.enabled ? 'text-emerald-600' : 'text-slate-500'}`}>
                  {scheduler.enabled ? 'ВКЛЮЧЁН' : 'ВЫКЛЮЧЕН'}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Интервал</p>
                <p className="font-semibold text-slate-800">{scheduler.intervalMinutes} мин</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Тиков выполнено</p>
                <p className="font-semibold text-slate-800">{scheduler.stats?.ticksExecuted || 0}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Пропущено (нет сессий)</p>
                <p className="font-semibold text-amber-600">{scheduler.stats?.skippedNoSession || 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Monitor Info */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Activity className="w-3.5 h-3.5" />
            <span>Монитор проверяет сессии каждые 2 мин.</span>
            <span>Проверок: {standby?.checkCount || 0}</span>
            {standby?.lastCheckAt && (
              <span>Последняя: {new Date(standby.lastCheckAt).toLocaleTimeString()}</span>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
