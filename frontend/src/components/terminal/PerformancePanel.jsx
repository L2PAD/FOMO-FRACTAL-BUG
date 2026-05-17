import React, { useEffect, useState } from 'react';
import { TrendingUp } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const PerformancePanel = ({ lang = 'ru' }) => {
  const [data, setData] = useState(null);

  const t = (ru, en) => (lang === 'ru' ? ru : en);

  const load = async () => {
    try {
      const res = await fetch(`${API_URL}/api/trading/performance`);
      const json = await res.json();
      if (json.ok) {
        setData(json.performance || {});
      }
    } catch (error) {
      console.error('Performance fetch error:', error);
    }
  };

  useEffect(() => {
    load();
    const i = setInterval(load, 5000);
    return () => clearInterval(i);
  }, []);

  if (!data) {
    return (
      <div className="bg-white rounded-xl p-4">
        <div className="text-sm text-[hsl(var(--fg-3))]">{t('Загрузка...', 'Loading...')}</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl p-4" data-testid="performance-panel">
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp className="w-4 h-4 text-[hsl(var(--accent))]" />
        <div className="text-xs font-semibold uppercase tracking-wide text-[hsl(var(--fg))]">{t('ПРОИЗВОДИТЕЛЬНОСТЬ', 'PERFORMANCE')}</div>
      </div>

      <div className="space-y-2">
        <Metric label={t('Всего сделок', 'Total trades')} value={data.total_trades || 0} />
        <Metric label={t('Винрейт', 'Win rate')} value={`${((data.win_rate || 0) * 100).toFixed(1)}%`} />
        <Metric 
          label={t('PnL', 'PnL')} 
          value={`$${(data.total_pnl || 0).toFixed(2)}`}
          valueColor={(data.total_pnl || 0) >= 0 ? 'text-[hsl(var(--pos))]' : 'text-[hsl(var(--neg))]'}
        />
      </div>
    </div>
  );
};

const Metric = ({ label, value, valueColor = 'text-[hsl(var(--fg))]' }) => {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-[hsl(var(--fg-3))]">{label}</span>
      <span className={`text-sm font-semibold tabular-nums ${valueColor}`}>{value}</span>
    </div>
  );
};

export default PerformancePanel;
