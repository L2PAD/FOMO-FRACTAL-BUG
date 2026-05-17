import React, { useState, useEffect } from 'react';
import { Power } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const AutoTradingToggle = ({ lang = 'ru' }) => {
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(false);

  const t = (ru, en) => (lang === 'ru' ? ru : en);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/trading/autotrading/status`);
      const data = await res.json();
      
      if (data.ok && data.autotrading) {
        setEnabled(data.autotrading.enabled);
      }
    } catch (error) {
      console.error('AutoTrading status fetch error:', error);
    }
  };

  const toggle = async () => {
    setLoading(true);
    
    try {
      const res = await fetch(`${API_URL}/api/trading/autotrading/${enabled ? 'disable' : 'enable'}`, {
        method: 'POST',
      });
      const data = await res.json();
      
      if (data.ok) {
        setEnabled(!enabled);
      }
    } catch (error) {
      console.error('AutoTrading toggle error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-white rounded-xl p-4" data-testid="terminal-auto-trading-switch">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-[hsl(var(--fg))]">{t('АВТОТРЕЙДИНГ', 'AUTO TRADING')}</div>
        <Power className={`w-4 h-4 ${enabled ? 'text-[hsl(var(--pos))]' : 'text-[hsl(var(--fg-3))]'}`} />
      </div>

      <button
        onClick={toggle}
        disabled={loading}
        className={`w-full px-4 py-3 rounded-lg font-medium text-sm transition-all ${
          enabled
            ? 'bg-[hsl(var(--accent))] text-white hover:opacity-90'
            : 'bg-gray-100 text-[hsl(var(--fg))] hover:bg-gray-200'
        } disabled:opacity-50`}
      >
        {loading ? t('Загрузка...', 'Loading...') : enabled ? t('Остановить', 'Stop') : t('Запустить', 'Start')}
      </button>

      <div className="mt-2 text-xs text-center text-[hsl(var(--fg-3))]">
        {t('Статус', 'Status')}: {enabled ? t('Активен', 'Active') : t('Остановлен', 'Stopped')}
      </div>
    </div>
  );
};

export default AutoTradingToggle;
