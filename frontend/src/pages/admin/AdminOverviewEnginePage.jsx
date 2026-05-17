/**
 * Decision Engine — Пороги, гейты и управление заморозкой
 */
import React, { useState, useEffect, useCallback } from 'react';
import AdminLayout from '../../components/admin/AdminLayout';
import { Button } from '../../components/ui/button';
import {
  Settings, Lock, Unlock, AlertTriangle, RotateCcw, Save, Check,
  Loader2, Sliders, ShieldAlert, Gauge, BarChart3,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const THRESHOLD_GROUPS = [
  {
    key: 'signals', label: 'Пороги сигналов', icon: Sliders,
    fields: [
      { key: 'executionThreshold', label: 'Порог исполнения', min: 0, max: 1, step: 0.05, tooltip: 'Минимальный score для исполнения сигнала' },
      { key: 'lowActivityThreshold', label: 'Порог низкой активности', min: 0, max: 1, step: 0.05, tooltip: 'Порог низкой активности рынка' },
    ],
  },
  {
    key: 'decision', label: 'Параметры решений', icon: Gauge,
    fields: [
      { key: 'confidenceFloor', label: 'Минимальная уверенность', min: 0, max: 1, step: 0.05, tooltip: 'Минимальная уверенность для принятия решения' },
      { key: 'strengthMultiplier', label: 'Множитель силы', min: 0.1, max: 5, step: 0.1, tooltip: 'Множитель силы сигнала' },
    ],
  },
  {
    key: 'macroGates', label: 'Макро-гейты', icon: ShieldAlert, danger: true,
    fields: [
      { key: 'blockOnExtremeFear', label: 'Блокировка при страхе', min: 0, max: 1, step: 1, tooltip: 'Блокировать торговлю при экстремальном страхе' },
      { key: 'blockOnExtremeGreed', label: 'Блокировка при жадности', min: 0, max: 1, step: 1, tooltip: 'Блокировать торговлю при экстремальной жадности' },
    ],
  },
  {
    key: 'altOutlook', label: 'Альткоин-ротация', icon: BarChart3,
    fields: [
      { key: 'rotationThreshold', label: 'Порог ротации', min: 0, max: 100, step: 5, tooltip: 'Порог ротации альткоинов' },
      { key: 'dominanceWeight', label: 'Вес доминирования', min: 0, max: 1, step: 0.05, tooltip: 'Вес доминирования BTC в расчёте' },
    ],
  },
];

export default function AdminOverviewEnginePage() {
  const [config, setConfig] = useState(null);
  const [defaults, setDefaults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [savedGroup, setSavedGroup] = useState(null);
  const [freezeReason, setFreezeReason] = useState('');
  const [error, setError] = useState(null);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/admin/config`);
      const json = await res.json();
      if (json.ok) { setConfig(json.config); setDefaults(json.defaults); setError(null); }
    } catch { setError('Не удалось загрузить конфигурацию'); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const handleChange = (group, field, value) => {
    setConfig(prev => ({ ...prev, [group]: { ...prev[group], [field]: parseFloat(value) } }));
  };

  const handleSave = async (groupKey) => {
    try {
      await fetch(`${API}/api/admin/config`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [groupKey]: config[groupKey] }),
      });
      setSavedGroup(groupKey);
      setTimeout(() => setSavedGroup(null), 1500);
    } catch {}
  };

  const handleReset = (groupKey) => {
    if (defaults?.[groupKey]) setConfig(prev => ({ ...prev, [groupKey]: { ...defaults[groupKey] } }));
  };

  const handleFreeze = async () => {
    await fetch(`${API}/api/admin/freeze`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: freezeReason || 'Manual freeze' }),
    });
    fetchConfig();
  };

  const handleUnfreeze = async () => {
    await fetch(`${API}/api/admin/unfreeze`, { method: 'POST' });
    fetchConfig();
  };

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6 space-y-6" data-testid="decision-engine-page">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Settings className="w-5 h-5 text-indigo-600" />
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Decision Engine</h1>
            <p className="text-xs text-gray-500">Пороги, гейты и управление заморозкой</p>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-3 p-4 bg-red-50/70 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-red-600" /> <span className="text-sm text-red-800">{error}</span>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
          </div>
        ) : !config ? (
          <div className="p-8 text-center text-gray-500">Не удалось загрузить конфигурацию</div>
        ) : (
          <>
            {/* Freeze Engine */}
            <div className={`p-5 rounded-lg ${config.frozen ? 'bg-red-50/70' : 'bg-gray-50/70'}`}
              data-testid="freeze-section"
              title="При активации система возвращает кэшированный snapshot, без пересчёта">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {config.frozen ? <Lock className="w-4 h-4 text-red-600" /> : <Unlock className="w-4 h-4 text-green-600" />}
                  <span className="text-sm font-semibold text-slate-900">Freeze Engine</span>
                  {config.frozen && <span className="text-xs font-bold text-red-600">ACTIVE</span>}
                </div>
                {config.frozen ? (
                  <Button variant="ghost" size="sm" onClick={handleUnfreeze} data-testid="unfreeze-btn"
                    className="text-gray-600 hover:bg-gray-100">
                    <Unlock className="w-3.5 h-3.5 mr-1" /> Разморозить
                  </Button>
                ) : (
                  <div className="flex items-center gap-2">
                    <input value={freezeReason} onChange={e => setFreezeReason(e.target.value)}
                      placeholder="Причина..."
                      className="px-2 py-1 rounded-lg text-sm w-40 outline-none bg-gray-50 text-slate-700" />
                    <Button variant="destructive" size="sm" onClick={handleFreeze} data-testid="freeze-btn">
                      <Lock className="w-3.5 h-3.5 mr-1" /> Заморозить
                    </Button>
                  </div>
                )}
              </div>
              {config.frozen && (
                <p className="text-xs text-gray-500">Заморожено: {config.frozenAt} | Причина: {config.frozenReason}</p>
              )}
              <p className="text-xs text-gray-400 mt-1">При заморозке все эндпоинты возвращают последний кэшированный снапшот</p>
            </div>

            {/* Threshold Groups */}
            <div className="space-y-5">
              {THRESHOLD_GROUPS.map(group => {
                const Icon = group.icon;
                return (
                  <div key={group.key}
                    className={`p-5 rounded-lg ${group.danger ? 'bg-red-50/70' : 'bg-gray-50/70'}`}
                    data-testid={`engine-group-${group.key}`}>
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <Icon className={`w-4 h-4 ${group.danger ? 'text-red-500' : 'text-indigo-500'}`} />
                        <span className="text-sm font-semibold text-slate-900">{group.label}</span>
                        {group.danger && <AlertTriangle className="w-3 h-3 text-red-500" />}
                        {savedGroup === group.key && (
                          <span className="text-xs font-bold text-green-600 animate-pulse flex items-center gap-1">
                            <Check className="w-3 h-3" /> Сохранено
                          </span>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <Button variant="ghost" size="sm" onClick={() => handleReset(group.key)}
                          className="text-gray-500 hover:bg-gray-100" data-testid={`reset-${group.key}`}>
                          <RotateCcw className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleSave(group.key)}
                          className="text-indigo-600 hover:bg-indigo-50"
                          data-testid={`save-${group.key}`}>
                          <Save className="w-3.5 h-3.5 mr-1" /> Сохранить
                        </Button>
                      </div>
                    </div>
                    <div className="space-y-4">
                      {group.fields.map(field => {
                        const val = config[group.key]?.[field.key] ?? 0;
                        const defVal = defaults?.[group.key]?.[field.key];
                        const isChanged = defVal !== undefined && Math.abs(val - defVal) > 0.001;
                        return (
                          <div key={field.key}>
                            <div className="flex items-center justify-between mb-1.5">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-medium text-slate-700">{field.label}</span>
                                {isChanged && <span className="w-1.5 h-1.5 rounded-full bg-amber-400" title="Изменено" />}
                              </div>
                              <div className="flex items-center gap-2">
                                <input type="number" value={val} step={field.step} min={field.min} max={field.max}
                                  onChange={e => handleChange(group.key, field.key, e.target.value)}
                                  className="w-[70px] text-right font-bold px-2 py-1 rounded-lg text-sm outline-none bg-gray-50 text-slate-900" />
                                {defVal !== undefined && (
                                  <span className="text-xs text-gray-300">def: {defVal}</span>
                                )}
                              </div>
                            </div>
                            <input type="range" value={val} step={field.step} min={field.min} max={field.max}
                              onChange={e => handleChange(group.key, field.key, e.target.value)}
                              className="w-full h-1 rounded-full appearance-none cursor-pointer"
                              style={{ background: '#e2e8f0', accentColor: group.danger ? '#dc2626' : '#6366f1' }} />
                            <p className="text-xs text-gray-400 mt-0.5">{field.tooltip}</p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </AdminLayout>
  );
}
