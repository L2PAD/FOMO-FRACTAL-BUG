/**
 * Карточка Governance — статус управления моделью
 */

import React from 'react';
import { Shield, Lock, Unlock, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';

const modeConfig = {
  NORMAL: { 
    bg: 'bg-gradient-to-br from-green-50 to-emerald-50', 
    border: 'border-green-200', 
    text: 'text-green-700', 
    badge: 'bg-green-100 text-green-700',
    icon: CheckCircle,
    label: 'Норма'
  },
  PROTECTION_MODE: { 
    bg: 'bg-gradient-to-br from-amber-50 to-yellow-50', 
    border: 'border-amber-300', 
    text: 'text-amber-700', 
    badge: 'bg-amber-100 text-amber-700',
    icon: Shield,
    label: 'Защитный режим'
  },
  FROZEN_ONLY: { 
    bg: 'bg-gradient-to-br from-blue-50 to-indigo-50', 
    border: 'border-blue-300', 
    text: 'text-blue-700', 
    badge: 'bg-blue-100 text-blue-700',
    icon: Lock,
    label: 'Заморожено'
  },
  HALT_TRADING: { 
    bg: 'bg-gradient-to-br from-red-50 to-rose-50', 
    border: 'border-red-400', 
    text: 'text-red-800', 
    badge: 'bg-red-200 text-red-800',
    icon: AlertTriangle,
    label: 'Торговля остановлена'
  },
};

export function GovernanceCard({ governance }) {
  if (!governance) return null;
  
  const mode = modeConfig[governance.mode] || modeConfig.NORMAL;
  const ModeIcon = mode.icon;
  
  return (
    <div 
      className={`rounded-2xl border-2 ${mode.border} ${mode.bg} p-5 transition-all duration-300 hover:shadow-lg`}
      data-testid="governance-card"
    >
      {/* Заголовок */}
      <div className="flex items-center justify-between mb-4">
        <h3 
          className="text-sm font-bold text-gray-700 uppercase tracking-wider"
          title="Режим управления моделью: определяет доступные операции"
        >
          Governance
        </h3>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${mode.badge}`}>
          <ModeIcon className="w-4 h-4" />
          <span className="text-sm font-bold">{mode.label}</span>
        </div>
      </div>
      
      {/* Статусы */}
      <div className="space-y-3">
        {/* Контракт */}
        <div className="flex items-center justify-between p-3 bg-white/60 rounded-xl">
          <span 
            className="text-sm text-gray-600 font-medium"
            title="Статус заморозки: заблокированы ли изменения модели"
          >
            Контракт
          </span>
          <div className={`flex items-center gap-2 px-3 py-1 rounded-lg ${
            governance.freeze?.isFrozen 
              ? 'bg-blue-100 text-blue-700' 
              : 'bg-gray-100 text-gray-600'
          }`}>
            {governance.freeze?.isFrozen ? (
              <Lock className="w-4 h-4" />
            ) : (
              <Unlock className="w-4 h-4" />
            )}
            <span className="text-sm font-bold">
              {governance.freeze?.isFrozen ? 'Заморожен' : 'Активен'}
            </span>
          </div>
        </div>
        
        {/* Ограничители */}
        <div className="flex items-center justify-between p-3 bg-white/60 rounded-xl">
          <span 
            className="text-sm text-gray-600 font-medium"
            title="Проверка лимитов риска и ограничений модели"
          >
            Ограничители
          </span>
          <div className={`flex items-center gap-2 px-3 py-1 rounded-lg ${
            governance.guardrails?.valid 
              ? 'bg-green-100 text-green-700' 
              : 'bg-red-100 text-red-700'
          }`}>
            {governance.guardrails?.valid ? (
              <CheckCircle className="w-4 h-4" />
            ) : (
              <XCircle className="w-4 h-4" />
            )}
            <span className="text-sm font-bold">
              {governance.guardrails?.valid 
                ? 'В норме' 
                : `${governance.guardrails?.violations?.length || 0} нарушений`}
            </span>
          </div>
        </div>
        
        {/* Активный пресет */}
        <div className="flex items-center justify-between p-3 bg-white/60 rounded-xl">
          <span 
            className="text-sm text-gray-600 font-medium"
            title="Текущий набор параметров модели"
          >
            Пресет
          </span>
          <span className="text-sm font-mono font-bold text-gray-800 px-3 py-1 bg-gray-100 rounded-lg">
            {governance.activePreset || 'По умолчанию'}
          </span>
        </div>
      </div>
      
      {/* Предупреждение о защитном режиме */}
      {governance.protectionMode && (
        <div className="mt-4 p-3 bg-amber-100 rounded-xl border border-amber-200 flex items-center gap-3">
          <Shield className="w-5 h-5 text-amber-600 flex-shrink-0" />
          <p className="text-sm text-amber-800 font-medium">
            Активирован защитный режим — торговля ограничена
          </p>
        </div>
      )}
    </div>
  );
}

export default GovernanceCard;
