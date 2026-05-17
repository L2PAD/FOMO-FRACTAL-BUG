/**
 * Карточка Health — статус здоровья модели
 */

import React from 'react';
import { Activity, TrendingDown, TrendingUp, AlertTriangle } from 'lucide-react';

const healthColors = {
  HEALTHY: { 
    bg: 'bg-gradient-to-br from-green-50 to-emerald-50', 
    border: 'border-green-200', 
    text: 'text-green-700', 
    dot: 'bg-green-500',
    barBg: 'bg-green-100',
    icon: TrendingUp,
    label: 'Здорова'
  },
  WATCH: { 
    bg: 'bg-gradient-to-br from-amber-50 to-yellow-50', 
    border: 'border-amber-200', 
    text: 'text-amber-700', 
    dot: 'bg-amber-500',
    barBg: 'bg-amber-100',
    icon: Activity,
    label: 'Наблюдение'
  },
  ALERT: { 
    bg: 'bg-gradient-to-br from-orange-50 to-amber-50', 
    border: 'border-orange-200', 
    text: 'text-orange-700', 
    dot: 'bg-orange-500',
    barBg: 'bg-orange-100',
    icon: AlertTriangle,
    label: 'Предупреждение'
  },
  CRITICAL: { 
    bg: 'bg-gradient-to-br from-red-50 to-rose-50', 
    border: 'border-red-300', 
    text: 'text-red-700', 
    dot: 'bg-red-500',
    barBg: 'bg-red-100',
    icon: TrendingDown,
    label: 'Критично'
  },
  BOOTSTRAP: {
    bg: 'bg-gradient-to-br from-gray-50 to-slate-50',
    border: 'border-gray-200',
    text: 'text-gray-600',
    dot: 'bg-gray-400',
    barBg: 'bg-gray-100',
    icon: Activity,
    label: 'Накопление данных'
  }
};

const severityLabels = {
  OK: 'Норма',
  WARN: 'Внимание',
  ALERT: 'Тревога',
  CRITICAL: 'Критично'
};

const severityConfig = {
  OK: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
  WARN: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  ALERT: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
  CRITICAL: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
};

export function HealthCard({ health }) {
  if (!health) return null;
  
  // Если мало данных — показываем BOOTSTRAP
  const hasInsufficientSamples = (health.sampleCount ?? 0) < 10;
  const currentState = hasInsufficientSamples ? 'BOOTSTRAP' : health.state;
  const colors = healthColors[currentState] || healthColors.HEALTHY;
  const Icon = colors.icon;
  
  const rawScore = health.score ?? health.hitRate ?? null;
  const score = hasInsufficientSamples ? null : (rawScore !== null ? rawScore * 100 : null);
  const isValidScore = score !== null && !isNaN(score);
  
  return (
    <div 
      className={`rounded-2xl border-2 ${colors.border} ${colors.bg} p-5 transition-all duration-300 hover:shadow-lg`}
      data-testid="health-card"
    >
      {/* Заголовок */}
      <div className="flex items-center justify-between mb-4">
        <h3 
          className="text-sm font-bold text-gray-700 uppercase tracking-wider"
          title="Общее состояние модели на основе метрик точности"
        >
          System Health
        </h3>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${colors.barBg}`}>
          <span className={`w-2 h-2 rounded-full ${colors.dot} animate-pulse`}></span>
          <Icon className={`w-4 h-4 ${colors.text}`} />
          <span className={`text-sm font-bold ${colors.text}`}>
            {colors.label}
          </span>
        </div>
      </div>
      
      {/* Оценка */}
      <div className="mb-4">
        <div className="flex items-baseline justify-between mb-2">
          <span 
            className="text-sm text-gray-500 font-medium"
            title="Процент успешных прогнозов"
          >
            Оценка
          </span>
          <div className="flex items-baseline gap-1">
            {isValidScore ? (
              <>
                <span className={`text-4xl font-black ${colors.text}`}>{score.toFixed(0)}</span>
                <span className={`text-lg font-bold ${colors.text}`}>%</span>
              </>
            ) : (
              <span className="text-2xl font-bold text-gray-400">—</span>
            )}
          </div>
        </div>
        
        {/* Прогресс-бар */}
        <div className="relative">
          <div className="w-full bg-white/60 rounded-full h-3 overflow-hidden shadow-inner">
            <div 
              className={`h-3 rounded-full ${isValidScore ? colors.dot : 'bg-gray-300'} transition-all duration-700 ease-out`}
              style={{ width: isValidScore ? `${score}%` : '0%' }}
            ></div>
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-[10px] text-gray-400">0%</span>
            <span className="text-[10px] text-amber-500 font-medium">60%</span>
            <span className="text-[10px] text-green-500 font-medium">80%</span>
            <span className="text-[10px] text-gray-400">100%</span>
          </div>
        </div>
        
        {/* Уведомление о недостатке данных */}
        {hasInsufficientSamples && (
          <p className="text-xs text-gray-500 mt-2 text-center">
            Система запущена. Ожидается накопление данных для расчета метрик.
          </p>
        )}
      </div>
      
      {/* Описание */}
      {health.headline && (
        <div className="mb-4 p-3 bg-white/50 rounded-xl border border-gray-100">
          <p className="text-sm text-gray-700 leading-relaxed">{health.headline}</p>
        </div>
      )}
      
      {/* Основные риски */}
      <div>
        <p 
          className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2"
          title="Ключевые факторы влияющие на здоровье модели"
        >
          Основные риски
        </p>
        <div className="space-y-2">
          {health.topRisks?.length > 0 ? (
            health.topRisks.map((risk, i) => {
              const sevConfig = severityConfig[risk.severity] || severityConfig.OK;
              return (
                <div 
                  key={i} 
                  className={`flex items-center justify-between p-2.5 rounded-xl ${sevConfig.bg} border ${sevConfig.border}`}
                >
                  <span className="text-sm text-gray-700 font-medium">{risk.key}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-mono font-bold text-gray-800">
                      {typeof risk.value === 'number' ? risk.value.toFixed(2) : risk.value}
                    </span>
                    <span className={`text-xs px-2.5 py-1 rounded-lg font-bold ${sevConfig.text} bg-white/60`}>
                      {severityLabels[risk.severity] || risk.severity}
                    </span>
                  </div>
                </div>
              );
            })
          ) : (
            <p className="text-sm text-gray-400 italic">Нет данных о рисках</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default HealthCard;
