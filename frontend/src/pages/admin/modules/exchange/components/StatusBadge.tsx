import React from 'react';
import { ReliabilityLevel } from '../types/exchangeAdmin.types';

const levelStyles: Record<ReliabilityLevel, string> = {
  OK: 'text-emerald-600',
  WARN: 'text-amber-600',
  DEGRADED: 'text-orange-600',
  CRITICAL: 'text-red-600',
  UNKNOWN: 'text-slate-500',
};

interface StatusBadgeProps {
  level: ReliabilityLevel;
  className?: string;
}

export default function StatusBadge({ level, className = '' }: StatusBadgeProps) {
  const color = levelStyles[level] || levelStyles.UNKNOWN;
  
  return (
    <span className={`text-sm font-semibold ${color} ${className}`}>
      {level}
    </span>
  );
}
