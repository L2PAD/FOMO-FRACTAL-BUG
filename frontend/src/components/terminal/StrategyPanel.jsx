import React, { useEffect, useState } from 'react';
import { Activity } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const StrategyPanel = ({ lang = 'ru' }) => {
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);

  const t = (ru, en) => (lang === 'ru' ? ru : en);

  const load = async () => {
    try {
      const statsRes = await fetch(`${API_URL}/api/strategy/stats`);
      const statsJson = await statsRes.json();

      if (statsJson.ok) {
        setStats(statsJson.strategies || {});
      }
    } catch (error) {
      console.error('Strategy stats error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="bg-white rounded-xl p-4">
        <div className="text-sm text-[hsl(var(--fg-3))]">{t('Загрузка...', 'Loading...')}</div>
      </div>
    );
  }

  const strategies = Object.entries(stats);

  return (
    <div className="bg-white rounded-xl p-4" data-testid="strategy-panel">
      <div className="flex items-center gap-2 mb-3">
        <Activity className="w-4 h-4 text-[hsl(var(--accent))]" />
        <div className="text-xs font-semibold uppercase tracking-wide text-[hsl(var(--fg))]">{t('СТРАТЕГИИ', 'STRATEGIES')}</div>
      </div>

      <div className="space-y-2">
        {strategies.length === 0 ? (
          <div className="text-sm text-[hsl(var(--fg-3))] py-4">{t('Нет стратегий', 'No strategies')}</div>
        ) : (
          strategies.map(([name, stat]) => (
            <div key={name} className="bg-gray-50 rounded-lg px-3 py-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-[hsl(var(--fg))]">{name}</span>
                <span className={`text-sm font-semibold tabular-nums ${stat.pnl >= 0 ? 'text-[hsl(var(--pos))]' : 'text-[hsl(var(--neg))]'}`}>
                  {stat.pnl >= 0 ? '+' : ''}{stat.pnl?.toFixed(2) || '0.00'}
                </span>
              </div>
              <div className="text-xs text-[hsl(var(--fg-3))] mt-1 tabular-nums">
                {t('Сделок', 'Trades')}: {stat.trades || 0} | {t('Винрейт', 'Win rate')}: {((stat.win_rate || 0) * 100).toFixed(0)}%
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default StrategyPanel;
