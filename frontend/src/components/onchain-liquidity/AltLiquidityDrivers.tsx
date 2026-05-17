/**
 * Alt Liquidity Drivers
 * ======================
 * 
 * PHASE 3: "Why this regime?" panel showing drivers
 */

import React from 'react';
import { MessageCircle, ChevronRight } from 'lucide-react';

interface Props {
  drivers: string[];
}

export function AltLiquidityDrivers({ drivers }: Props) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm p-5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <MessageCircle className="w-5 h-5 text-blue-400" />
        <span className="text-sm font-medium text-gray-300">Why this regime?</span>
      </div>

      {/* Drivers List */}
      {drivers && drivers.length > 0 ? (
        <ul className="space-y-2" data-testid="liquidity-drivers">
          {drivers.slice(0, 6).map((driver, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-gray-400">
              <ChevronRight className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
              <span>{driver}</span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="text-sm text-gray-500 italic">
          No dominant drivers detected
        </div>
      )}
    </div>
  );
}
