/**
 * LARE v2 Drivers Block
 * ======================
 * 
 * PHASE 4: "Why this regime?" — compact bullet list
 * - Без лишних подписей
 * - Только ключевые драйверы
 */

import React from 'react';

interface Props {
  regime: string;
  drivers: string[];
}

export function LareV2Drivers({ regime, drivers }: Props) {
  // Не рендерить если нет драйверов
  if (!drivers || drivers.length === 0) return null;

  // Максимум 3 драйвера
  const topDrivers = drivers.slice(0, 3);

  // Форматировать regime для заголовка
  const regimeLabel = regime.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase());

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4" data-testid="lare-v2-drivers">
      <div className="text-sm font-medium text-gray-300 mb-3">
        Why {regimeLabel}?
      </div>

      <ul className="space-y-2">
        {topDrivers.map((driver, i) => (
          <li key={i} className="flex items-start gap-2 text-sm">
            <span className="text-blue-400 mt-0.5">›</span>
            <span className="text-gray-300">{driver}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
