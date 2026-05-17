/**
 * BLOCK 76.2.2 — Weekly Cron Control Card
 * 
 * Shows cron status, next run, and allows manual trigger with protection check.
 */

import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

export function WeeklyCronCard() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [protectionResult, setProtectionResult] = useState(null);
  const [triggerResult, setTriggerResult] = useState(null);
  
  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/fractal/v2.1/admin/weekly-cron/status`);
      const data = await res.json();
      setStatus(data);
    } catch (err) {
      console.error('Failed to fetch cron status:', err);
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 60000);
    return () => clearInterval(interval);
  }, [fetchStatus]);
  
  const handleCheck = async () => {
    setChecking(true);
    setProtectionResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/fractal/v2.1/admin/weekly-cron/check`, {
        method: 'POST'
      });
      const data = await res.json();
      setProtectionResult(data);
    } catch (err) {
      setProtectionResult({ error: err.message });
    } finally {
      setChecking(false);
    }
  };
  
  const handleTrigger = async () => {
    if (!window.confirm('Send Weekly Digest now? This will bypass schedule but respect protections.')) {
      return;
    }
    setTriggering(true);
    setTriggerResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/fractal/v2.1/admin/weekly-cron/trigger`, {
        method: 'POST'
      });
      const data = await res.json();
      setTriggerResult(data);
      await fetchStatus();
    } catch (err) {
      setTriggerResult({ error: err.message });
    } finally {
      setTriggering(false);
    }
  };
  
  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="animate-pulse h-24 bg-gray-100 rounded"></div>
      </div>
    );
  }
  
  const nextRunDate = status?.nextRun ? new Date(status.nextRun) : null;
  const lastRunDate = status?.lastRun ? new Date(status.lastRun) : null;
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid="weekly-cron-card">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">📅</span>
            <span className="font-semibold text-gray-800">Планировщик рассылки</span>
          </div>
          <span className={`text-xs px-2 py-1 rounded-full font-medium ${
            status?.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-600'
          }`}>
            {status?.enabled ? 'ВКЛЮЧЁН' : 'ВЫКЛЮЧЕН'}
          </span>
        </div>
      </div>
      
      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Schedule Info */}
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <div className="text-gray-500 text-xs mb-1">Следующий запуск</div>
            <div className="font-medium text-gray-800">
              {nextRunDate ? nextRunDate.toLocaleString('ru-RU') : '—'}
            </div>
          </div>
          <div>
            <div className="text-gray-500 text-xs mb-1">Последний запуск</div>
            <div className="font-medium text-gray-800">
              {lastRunDate ? lastRunDate.toLocaleString('ru-RU') : 'Никогда'}
            </div>
          </div>
        </div>
        
        {/* Config */}
        <div className="text-xs text-gray-500 bg-gray-50 rounded-lg p-2">
          <div className="flex items-center justify-between">
            <span>Расписание: Воскресенье {status?.config?.hour}:{String(status?.config?.minute || 0).padStart(2, '0')} UTC</span>
            <span>Мин. выборка: {status?.config?.minSamples}</span>
          </div>
        </div>
        
        {/* Actions */}
        <div className="flex gap-2">
          <button
            onClick={handleCheck}
            disabled={checking}
            className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50 flex items-center justify-center gap-2"
            title="Проверить защиты перед отправкой"
          >
            {checking ? (
              <span className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
            ) : (
              <span>🔍</span>
            )}
            Проверить
          </button>
          <button
            onClick={handleTrigger}
            disabled={triggering}
            className="flex-1 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
            title="Отправить дайджест сейчас"
          >
            {triggering ? (
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <span>📤</span>
            )}
            Отправить
          </button>
        </div>
        
        {/* Protection Result */}
        {protectionResult && (
          <div className={`p-3 rounded-lg text-sm ${
            protectionResult.canSend 
              ? 'bg-emerald-50 border border-emerald-200' 
              : 'bg-amber-50 border border-amber-200'
          }`}>
            <div className="flex items-center gap-2">
              <span>{protectionResult.canSend ? '✅' : '⚠️'}</span>
              <span className={protectionResult.canSend ? 'text-emerald-700' : 'text-amber-700'}>
                {protectionResult.canSend ? 'Готово к отправке' : 'Заблокировано'}
              </span>
            </div>
            <div className="text-xs mt-1 text-gray-600">
              {protectionResult.reason}
            </div>
          </div>
        )}
        
        {/* Trigger Result */}
        {triggerResult && (
          <div className={`p-3 rounded-lg text-sm ${
            triggerResult.success 
              ? 'bg-emerald-50 border border-emerald-200' 
              : 'bg-red-50 border border-red-200'
          }`}>
            <div className="flex items-center gap-2">
              <span>{triggerResult.success ? '✅' : '❌'}</span>
              <span className={triggerResult.success ? 'text-emerald-700' : 'text-red-700'}>
                {triggerResult.success ? 'Дайджест отправлен!' : 'Ошибка отправки'}
              </span>
            </div>
            {triggerResult.result?.message && (
              <div className="text-xs mt-1 text-gray-600">
                {triggerResult.result.message}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default WeeklyCronCard;
