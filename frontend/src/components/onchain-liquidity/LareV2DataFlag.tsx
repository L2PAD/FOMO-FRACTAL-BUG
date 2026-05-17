/**
 * LARE v2 Data Flag
 * ==================
 * 
 * PHASE 2: Компактный alert под header
 * - Без цифр
 * - Без технической информации
 * - Только статус
 */

import React from 'react';
import { AlertTriangle, AlertCircle } from 'lucide-react';

interface Props {
  flags: string[];
  confidence: number;
}

export function LareV2DataFlag({ flags, confidence }: Props) {
  const hasLowData = flags.some(f => 
    f.includes('LOW_DATA') || 
    f.includes('LIMITED_DATA') || 
    f.includes('SINGLE_CHAIN')
  );
  
  const hasCritical = flags.some(f => 
    f.includes('NO_DATA') || 
    f.includes('CRITICAL')
  );

  const isLowConf = confidence < 0.3;

  // Не рендерим если всё хорошо
  if (!hasLowData && !hasCritical && !isLowConf) return null;

  const isCritical = hasCritical;
  const Icon = isCritical ? AlertCircle : AlertTriangle;
  
  // Простое сообщение без цифр
  const message = isCritical ? 'Critical Data Missing' :
                  hasLowData ? 'Low Data Coverage' :
                  'Low Confidence';

  return (
    <div 
      className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium ${
        isCritical 
          ? 'bg-red-500/10 border border-red-500/20 text-red-400'
          : 'bg-amber-500/10 border border-amber-500/20 text-amber-400'
      }`}
      data-testid="lare-v2-data-flag"
    >
      <Icon className="w-4 h-4" />
      <span>{message}</span>
    </div>
  );
}
