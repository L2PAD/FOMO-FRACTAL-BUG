import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, RefreshCw, AlertCircle, Target, Shield } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const MarketOpportunities = () => {
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastScan, setLastScan] = useState(null);
  const [error, setError] = useState(null);

  const fetchOpportunities = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`${API_URL}/api/market/opportunities`);
      const data = await response.json();
      
      if (data.opportunities) {
        setOpportunities(data.opportunities);
        setLastScan(data.last_scan);
      }
    } catch (err) {
      console.error('Failed to fetch opportunities:', err);
      setError('Не удалось загрузить данные');
    } finally {
      setLoading(false);
    }
  };

  const triggerScan = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/api/market/scan`, { method: 'POST' });
      const data = await response.json();
      
      if (data.signals) {
        setOpportunities(data.signals);
        setLastScan(new Date().toISOString());
      }
    } catch (err) {
      console.error('Scan failed:', err);
      setError('Сканирование не выполнено');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOpportunities();
    // Auto-refresh every 60 seconds
    const interval = setInterval(fetchOpportunities, 60000);
    return () => clearInterval(interval);
  }, []);

  const getDirectionColor = (direction) => {
    return direction === 'LONG' ? 'text-green-700' : 'text-red-700';
  };

  const getDirectionBg = (direction) => {
    return direction === 'LONG' ? 'bg-green-50' : 'bg-red-50';
  };

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.75) return 'text-green-700';
    if (confidence >= 0.65) return 'text-yellow-700';
    return 'text-gray-700';
  };

  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'только что';
    if (diffMins < 60) return `${diffMins}м назад`;
    return `${Math.floor(diffMins / 60)}ч назад`;
  };

  return (
    <div className="bg-white rounded-lg border border-[#e6eaf2]" style={{ boxShadow: '0px 1px 3px rgba(0,5,48,0.08)' }}>
      {/* Header */}
      <div className="px-5 py-3 border-b border-[#e6eaf2] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Target className="w-5 h-5 text-[#04A584]" />
          <h3 className="text-base font-semibold text-gray-900">Рыночные возможности</h3>
          <span className="text-xs text-gray-500 bg-gray-50 px-2 py-0.5 rounded">
            {opportunities.length} сигналов
          </span>
        </div>
        
        <div className="flex items-center gap-2">
          {lastScan && (
            <span className="text-xs text-gray-500">
              Обновлено: {formatTime(lastScan)}
            </span>
          )}
          <button
            onClick={triggerScan}
            disabled={loading}
            className="p-1.5 hover:bg-gray-50 rounded transition-colors disabled:opacity-50"
            data-testid="refresh-opportunities-btn"
          >
            <RefreshCw className={`w-4 h-4 text-gray-600 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        {error && (
          <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-3 py-2 rounded mb-3">
            <AlertCircle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        )}

        {loading && opportunities.length === 0 ? (
          <div className="text-center py-8">
            <div className="w-8 h-8 border-3 border-gray-200 border-t-[#04A584] rounded-full animate-spin mx-auto mb-2" />
            <p className="text-sm text-gray-500">Сканирование рынка...</p>
          </div>
        ) : opportunities.length === 0 ? (
          <div className="text-center py-8">
            <AlertCircle className="w-8 h-8 text-gray-400 mx-auto mb-2" />
            <p className="text-sm text-gray-500">Сигналов не найдено</p>
            <button
              onClick={triggerScan}
              className="mt-3 text-sm text-[#04A584] hover:text-[#03916e] font-medium"
            >
              Запустить сканирование
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left font-medium text-gray-600 pb-2 px-2">Актив</th>
                  <th className="text-left font-medium text-gray-600 pb-2 px-2">TF</th>
                  <th className="text-left font-medium text-gray-600 pb-2 px-2">Стратегия</th>
                  <th className="text-center font-medium text-gray-600 pb-2 px-2">Направление</th>
                  <th className="text-center font-medium text-gray-600 pb-2 px-2">Уверенность</th>
                  <th className="text-right font-medium text-gray-600 pb-2 px-2">Вход</th>
                  <th className="text-right font-medium text-gray-600 pb-2 px-2">Стоп</th>
                  <th className="text-right font-medium text-gray-600 pb-2 px-2">Цель</th>
                  <th className="text-left font-medium text-gray-600 pb-2 px-2">Обоснование</th>
                </tr>
              </thead>
              <tbody>
                {opportunities.map((opp, idx) => (
                  <tr
                    key={idx}
                    className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
                    data-testid={`opportunity-row-${idx}`}
                  >
                    {/* Symbol */}
                    <td className="py-2.5 px-2">
                      <span className="font-medium text-gray-900">
                        {opp.symbol.replace('USDT', '')}
                      </span>
                      <span className="text-xs text-gray-500 ml-1">USDT</span>
                    </td>
                    
                    {/* Timeframe */}
                    <td className="py-2.5 px-2">
                      <span className="text-xs bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded font-medium">
                        {opp.timeframe}
                      </span>
                    </td>
                    
                    {/* Strategy */}
                    <td className="py-2.5 px-2">
                      <span className="text-xs text-gray-600">
                        {opp.strategy.replace(/_/g, ' ')}
                      </span>
                    </td>
                    
                    {/* Direction */}
                    <td className="py-2.5 px-2 text-center">
                      <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded ${getDirectionBg(opp.direction)}`}>
                        {opp.direction === 'LONG' ? (
                          <TrendingUp className={`w-3.5 h-3.5 ${getDirectionColor(opp.direction)}`} />
                        ) : (
                          <TrendingDown className={`w-3.5 h-3.5 ${getDirectionColor(opp.direction)}`} />
                        )}
                        <span className={`text-xs font-medium ${getDirectionColor(opp.direction)}`}>
                          {opp.direction}
                        </span>
                      </div>
                    </td>
                    
                    {/* Confidence */}
                    <td className="py-2.5 px-2 text-center">
                      <span className={`text-sm font-semibold ${getConfidenceColor(opp.confidence)}`}>
                        {(opp.confidence * 100).toFixed(0)}%
                      </span>
                    </td>
                    
                    {/* Entry */}
                    <td className="py-2.5 px-2 text-right">
                      <span className="text-sm text-gray-900">
                        ${opp.entry_zone.toLocaleString()}
                      </span>
                    </td>
                    
                    {/* Stop */}
                    <td className="py-2.5 px-2 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Shield className="w-3 h-3 text-gray-400" />
                        <span className="text-sm text-gray-700">
                          ${opp.stop.toLocaleString()}
                        </span>
                      </div>
                    </td>
                    
                    {/* Target */}
                    <td className="py-2.5 px-2 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Target className="w-3 h-3 text-green-500" />
                        <span className="text-sm text-gray-700">
                          ${opp.target.toLocaleString()}
                        </span>
                      </div>
                    </td>
                    
                    {/* Reasoning */}
                    <td className="py-2.5 px-2">
                      <span className="text-xs text-gray-600 line-clamp-2">
                        {opp.reasoning}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default MarketOpportunities;
