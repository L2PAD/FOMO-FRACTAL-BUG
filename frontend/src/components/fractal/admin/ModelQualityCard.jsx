/**
 * Model Quality Score Card
 * 
 * Shows 0-100 score based on:
 * - hitRate (40%)
 * - avgAbsError percentile (30%)
 * - trend (20%)
 * - sampleCount weight (10%)
 */

import React, { useState, useEffect } from 'react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

function calculateScore(byHorizon, rolling) {
  if (!byHorizon || byHorizon.length === 0) {
    return { score: 0, breakdown: {}, status: 'NO_DATA' };
  }
  
  // Use 30d horizon as primary
  const h = byHorizon.find(x => x.horizon === '30d') || byHorizon[0];
  
  // Hit Rate Score (0-40 points)
  // 50% = 0, 60% = 20, 70% = 40
  const hitRateScore = Math.min(40, Math.max(0, (h.hitRate - 50) * 2));
  
  // Error Score (0-30 points)
  // <5% = 30, 5-15% = 20, 15-25% = 10, >25% = 0
  let errorScore = 0;
  if (h.avgAbsError < 5) errorScore = 30;
  else if (h.avgAbsError < 15) errorScore = 20;
  else if (h.avgAbsError < 25) errorScore = 10;
  
  // Trend Score (0-20 points)
  let trendScore = 0;
  if (h.trend === 'improving') trendScore = 20;
  else if (h.trend === 'stable') trendScore = 10;
  else if (h.trend === 'worsening') trendScore = 0;
  
  // Sample Score (0-10 points)
  // 100+ samples = 10, 50-100 = 5, <50 = 0
  let sampleScore = 0;
  if (h.sampleCount >= 100) sampleScore = 10;
  else if (h.sampleCount >= 50) sampleScore = 5;
  
  const totalScore = Math.round(hitRateScore + errorScore + trendScore + sampleScore);
  
  return {
    score: totalScore,
    breakdown: {
      hitRate: hitRateScore,
      error: errorScore,
      trend: trendScore,
      samples: sampleScore,
    },
    status: totalScore >= 60 ? 'GOOD' : totalScore >= 40 ? 'ACCEPTABLE' : 'NEEDS_ATTENTION',
  };
}

export function ModelQualityCard({ asset = 'btc' }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const assetLower = asset.toLowerCase();
  
  useEffect(() => {
    async function fetchData() {
      try {
        const [byHorizonRes, rollingRes] = await Promise.all([
          fetch(`${API_BASE}/api/admin/${assetLower}/drift/by-horizon?includeSeed=true`),
          fetch(`${API_BASE}/api/admin/${assetLower}/drift/rolling?horizon=30d&window=30&includeSeed=true`),
        ]);
        
        const byHorizon = await byHorizonRes.json();
        const rolling = await rollingRes.json();
        
        const result = calculateScore(byHorizon.byHorizon, rolling.points);
        setData({
          ...result,
          horizon: byHorizon.byHorizon?.[0],
          dataMode: byHorizon.dataMode,
        });
      } catch (err) {
        console.error('Error fetching model quality:', err);
      } finally {
        setLoading(false);
      }
    }
    
    fetchData();
  }, []);
  
  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/2 mb-4"></div>
          <div className="h-20 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }
  
  if (!data) {
    return null;
  }
  
  const statusColors = {
    GOOD: 'bg-green-500',
    ACCEPTABLE: 'bg-yellow-500',
    NEEDS_ATTENTION: 'bg-red-500',
    NO_DATA: 'bg-gray-400',
  };
  
  const statusLabels = {
    GOOD: 'Готова к продакшену',
    ACCEPTABLE: 'Приемлемо',
    NEEDS_ATTENTION: 'Требует внимания',
    NO_DATA: 'Нет данных',
  };
  
  return (
    <div 
      className="bg-white rounded-xl border border-gray-200 p-4" 
      data-testid="model-quality-card"
      title="Комплексная оценка качества модели на основе метрик точности, ошибок и тренда"
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-bold text-gray-900">Качество модели</h3>
        <span className={`px-2 py-1 text-xs rounded text-white ${statusColors[data.status]}`}>
          {statusLabels[data.status]}
        </span>
      </div>
      
      {/* Score Circle */}
      <div className="flex items-center gap-6">
        <div className="relative w-24 h-24">
          <svg className="w-24 h-24 transform -rotate-90" viewBox="0 0 36 36">
            <path
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              fill="none"
              stroke="#e5e7eb"
              strokeWidth="3"
            />
            <path
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              fill="none"
              stroke={data.score >= 60 ? '#22c55e' : data.score >= 40 ? '#eab308' : '#ef4444'}
              strokeWidth="3"
              strokeDasharray={`${data.score}, 100`}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-2xl font-bold text-gray-900">{data.score}</span>
          </div>
        </div>
        
        {/* Breakdown */}
        <div className="flex-1 space-y-1 text-sm">
          <div className="flex justify-between" title="Процент успешных прогнозов">
            <span className="text-gray-500">Точность</span>
            <span className="font-mono">{data.breakdown.hitRate}/40</span>
          </div>
          <div className="flex justify-between" title="Средняя ошибка прогноза">
            <span className="text-gray-500">Ошибка</span>
            <span className="font-mono">{data.breakdown.error}/30</span>
          </div>
          <div className="flex justify-between" title="Направление изменения качества">
            <span className="text-gray-500">Тренд</span>
            <span className="font-mono">{data.breakdown.trend}/20</span>
          </div>
          <div className="flex justify-between" title="Количество данных для анализа">
            <span className="text-gray-500">Выборка</span>
            <span className="font-mono">{data.breakdown.samples}/10</span>
          </div>
        </div>
      </div>
      
      {/* Data Mode Badge */}
      <div className="mt-3 text-xs text-gray-400 text-right">
        Данные: {data.dataMode === 'SEED' ? 'Тестовые' : data.dataMode === 'LIVE' ? 'Реальные' : data.dataMode || 'Live'}
      </div>
    </div>
  );
}

export default ModelQualityCard;
