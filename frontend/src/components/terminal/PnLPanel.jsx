import React, { useEffect, useState } from 'react';
import { DollarSign } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const PnLPanel = ({ lang = 'ru' }) => {
  const [data, setData] = useState(null);

  const t = (ru, en) => (lang === 'ru' ? ru : en);

  const load = async () => {
    try {
      const res = await fetch(`${API_URL}/api/trading/pnl`);
      const json = await res.json();
      if (json.ok) {
        setData(json.pnl || {});
      }
    } catch (error) {
      console.error('PnL fetch error:', error);
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
    <div className="bg-white rounded-xl p-4">
      <div className="flex items-center gap-2 mb-4">
        <DollarSign className="w-4 h-4 text-[hsl(var(--accent))]" />
        <div className="text-xs font-semibold uppercase tracking-wide text-[hsl(var(--fg))]">{t('ПРИБЫЛЬ И УБЫТОК', 'PROFIT & LOSS')}</div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <Metric label={t('Сегодня', 'Today')} value={`$${(data.today || 0).toFixed(2)}`} valueColor={(data.today || 0) >= 0 ? 'text-[hsl(var(--pos))]' : 'text-[hsl(var(--neg))]'} />
        <Metric label={t('Неделя', 'Week')} value={`$${(data.week || 0).toFixed(2)}`} valueColor={(data.week || 0) >= 0 ? 'text-[hsl(var(--pos))]' : 'text-[hsl(var(--neg))]'} />
        <Metric label={t('Месяц', 'Month')} value={`$${(data.month || 0).toFixed(2)}`} valueColor={(data.month || 0) >= 0 ? 'text-[hsl(var(--pos))]' : 'text-[hsl(var(--neg))]'} />
        <Metric label={t('Всего', 'Total')} value={`$${(data.total || 0).toFixed(2)}`} valueColor={(data.total || 0) >= 0 ? 'text-[hsl(var(--pos))]' : 'text-[hsl(var(--neg))]'} />
      </div>
    </div>
  );
};

const Metric = ({ label, value, valueColor = 'text-[hsl(var(--fg))]' }) => {
  return (
    <div>
      <div className="text-xs text-[hsl(var(--fg-3))] mb-1">{label}</div>
      <div className={`text-base font-semibold tabular-nums ${valueColor}`}>{value}</div>
    </div>
  );
};

export default PnLPanel;
