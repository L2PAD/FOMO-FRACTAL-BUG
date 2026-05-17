/**
 * Portfolio Overview — Capital-aware UI
 * Shows equity, balance, PnL, risk heat
 */

import React, { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, Shield, DollarSign } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const PortfolioOverview = ({ lang = 'ru' }) => {
  const [data, setData] = useState(null);

  const t = (ru, en) => (lang === 'ru' ? ru : en);

  const load = async () => {
    try {
      const res = await fetch(`${API_URL}/api/trading/portfolio`);
      const json = await res.json();
      if (json.ok && json.portfolio) {
        setData(json.portfolio);
      }
    } catch (error) {
      console.error('Portfolio fetch error:', error);
    }
  };

  useEffect(() => {
    load();
    const i = setInterval(load, 2000);
    return () => clearInterval(i);
  }, []);

  if (!data) {
    return (
      <div className="bg-white rounded-xl p-4">
        <div className="text-sm text-gray-500">{t('Загрузка портфеля...', 'Loading portfolio...')}</div>
      </div>
    );
  }

  const equity = data.equity || 10000;
  const balance = data.balance || 10000;
  const pnl = equity - balance;
  const riskHeat = data.risk_heat || 0;

  return (
    <div 
      className="bg-white rounded-xl p-4"
      data-testid="portfolio-overview"
    >
      <h3 className="text-xs font-semibold text-gray-900 uppercase tracking-wide mb-3">
        {t('ПОРТФЕЛЬ', 'PORTFOLIO')}
      </h3>

      <div className="grid grid-cols-2 gap-3">
        <Metric 
          label={t('Капитал', 'Equity')}
          value={`$${equity.toFixed(2)}`}
          icon={<DollarSign className="w-4 h-4 text-gray-900" />}
          testId="portfolio-total-capital"
        />
        <Metric 
          label={t('Баланс', 'Balance')}
          value={`$${balance.toFixed(2)}`}
          icon={<DollarSign className="w-4 h-4 text-gray-500" />}
        />

        <Metric
          label="PnL"
          value={`$${pnl.toFixed(2)}`}
          color={pnl >= 0 ? 'text-gray-900' : 'text-gray-900'}
          icon={pnl >= 0 
            ? <TrendingUp className="w-4 h-4 text-gray-900" />
            : <TrendingDown className="w-4 h-4 text-gray-900" />
          }
          testId="portfolio-pnl"
        />

        <Metric
          label={t('Риск', 'Risk Heat')}
          value={`${(riskHeat * 100).toFixed(0)}%`}
          color="text-gray-900"
          icon={<Shield className="w-4 h-4 text-gray-500" />}
        />
      </div>
    </div>
  );
};

const Metric = ({ label, value, color = 'text-gray-900', icon, testId }) => {
  return (
    <div className="bg-gray-50 rounded-lg p-3" data-testid={testId}>
      <div className="flex items-center gap-1.5 mb-1">
        {icon}
        <div className="text-xs text-gray-500">{label}</div>
      </div>
      <div className={`text-lg font-semibold ${color}`}>{value}</div>
    </div>
  );
};

export default PortfolioOverview;
