import React from 'react';

interface StatusBadgeProps {
  status: 'PASS' | 'BLOCK' | 'WARN' | 'OK' | 'CRITICAL' | 'UNKNOWN';
  size?: 'sm' | 'md';
}

export function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const colors: Record<string, string> = {
    PASS: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    OK: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    BLOCK: 'bg-amber-100 text-amber-700 border-amber-200',
    WARN: 'bg-amber-100 text-amber-700 border-amber-200',
    CRITICAL: 'bg-red-100 text-red-700 border-red-200',
    UNKNOWN: 'bg-slate-100 text-slate-600 border-slate-200',
  };

  const sizeClass = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';

  return (
    <span className={`${colors[status] || colors.UNKNOWN} ${sizeClass} rounded-full border font-medium`}>
      {status}
    </span>
  );
}
