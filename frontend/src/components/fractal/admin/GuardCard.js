/**
 * Карточка Guard — защита от катастрофических потерь
 */

import React from 'react';
import { ShieldAlert, ShieldCheck, AlertTriangle, Clock } from 'lucide-react';

const stateConfig = {
  OK: { 
    bg: 'bg-gradient-to-br from-green-50 to-emerald-50', 
    border: 'border-green-200', 
    bar: 'bg-green-500', 
    text: 'text-green-700',
    icon: ShieldCheck,
    label: 'Норма'
  },
  WARN: { 
    bg: 'bg-gradient-to-br from-amber-50 to-yellow-50', 
    border: 'border-amber-200', 
    bar: 'bg-amber-500', 
    text: 'text-amber-700',
    icon: AlertTriangle,
    label: 'Внимание'
  },
  ALERT: { 
    bg: 'bg-gradient-to-br from-orange-50 to-amber-50', 
    border: 'border-orange-300', 
    bar: 'bg-orange-500', 
    text: 'text-orange-700',
    icon: ShieldAlert,
    label: 'Тревога'
  },
  CRITICAL: { 
    bg: 'bg-gradient-to-br from-red-50 to-rose-50', 
    border: 'border-red-300', 
    bar: 'bg-red-500', 
    text: 'text-red-700',
    icon: ShieldAlert,
    label: 'Критично'
  },
};

const subscoreLabels = {
  accuracy: 'Точность',
  volatility: 'Волатильность',
  drawdown: 'Просадка',
  consistency: 'Стабильность',
  regime: 'Режим рынка',
};

export function GuardCard({ guard }) {
  if (!guard) return null;
  
  const config = stateConfig[guard.state] || stateConfig.OK;
  const Icon = config.icon;
  
  // Обработка отсутствующих данных
  const rawDegScore = guard.degenerationScore;
  const degScore = rawDegScore !== null && rawDegScore !== undefined ? rawDegScore * 100 : null;
  const isValidScore = degScore !== null && !isNaN(degScore);
  
  return (
    <div 
      className={`rounded-2xl border-2 ${config.border} ${config.bg} p-5 transition-all duration-300 hover:shadow-lg`}
      data-testid="guard-card"
    >
      {/* Заголовок */}
      <div className="flex items-center justify-between mb-4">
        <h3 
          className="text-sm font-bold text-gray-700 uppercase tracking-wider"
          title="Система защиты от катастрофических потерь модели"
        >
          Защита модели
        </h3>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/60 ${config.text}`}>
          <Icon className="w-4 h-4" />
          <span className="text-sm font-bold">{config.label}</span>
        </div>
      </div>
      
      {/* Уровень деградации */}
      <div className="mb-5">
        <div className="flex items-baseline justify-between mb-2">
          <span 
            className="text-sm text-gray-500 font-medium"
            title="Уровень ухудшения качества модели: чем выше, тем хуже"
          >
            Уровень деградации
          </span>
          <div className="flex items-baseline gap-1">
            {isValidScore ? (
              <>
                <span className={`text-3xl font-black ${config.text}`}>{degScore.toFixed(0)}</span>
                <span className={`text-lg font-bold ${config.text}`}>%</span>
              </>
            ) : (
              <span className="text-2xl font-bold text-gray-400">—</span>
            )}
          </div>
        </div>
        
        {/* Прогресс-бар с зонами */}
        <div className="relative mb-2">
          <div className="w-full bg-white/60 rounded-full h-4 overflow-hidden shadow-inner">
            <div className="absolute inset-0 flex">
              <div className="w-[55%] bg-green-100" title="Безопасная зона"></div>
              <div className="w-[20%] bg-amber-100" title="Зона внимания"></div>
              <div className="flex-1 bg-red-100" title="Опасная зона"></div>
            </div>
            <div 
              className={`h-4 ${isValidScore ? config.bar : 'bg-gray-300'} transition-all duration-700 ease-out relative z-10`}
              style={{ width: isValidScore ? `${degScore}%` : '0%' }}
            ></div>
          </div>
          
          {/* Метки зон */}
          <div className="flex justify-between mt-1.5 px-1">
            <span className="text-[10px] text-green-600 font-medium">Безопасно</span>
            <span className="text-[10px] text-amber-600 font-medium">55%</span>
            <span className="text-[10px] text-red-600 font-medium">75%</span>
            <span className="text-[10px] text-gray-400">100%</span>
          </div>
        </div>
      </div>
      
      {/* Компоненты оценки */}
      {guard.subscores && Object.keys(guard.subscores).length > 0 && (
        <div className="mb-4">
          <p 
            className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2"
            title="Компоненты, влияющие на общую оценку деградации"
          >
            Компоненты оценки
          </p>
          <div className="space-y-2">
            {Object.entries(guard.subscores).map(([key, value]) => {
              const percent = value * 100;
              const barColor = percent >= 70 ? 'bg-red-500' : percent >= 40 ? 'bg-amber-500' : 'bg-green-500';
              
              return (
                <div key={key} className="p-2 bg-white/50 rounded-xl">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-gray-600 font-medium">
                      {subscoreLabels[key] || key}
                    </span>
                    <span className="text-xs font-mono font-bold text-gray-700">{percent.toFixed(0)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
                    <div 
                      className={`h-1.5 ${barColor} transition-all duration-500`}
                      style={{ width: `${percent}%` }}
                    ></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
      
      {/* Предупреждение о блокировке */}
      {guard.latch?.active && (
        <div className="p-3 bg-amber-100 rounded-xl border border-amber-200 flex items-center gap-3">
          <Clock className="w-5 h-5 text-amber-600 flex-shrink-0" />
          <div>
            <p className="text-sm text-amber-800 font-medium">Временная блокировка активна</p>
            <p className="text-xs text-amber-600">
              До {new Date(guard.latch.until).toLocaleDateString('ru-RU')}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default GuardCard;
