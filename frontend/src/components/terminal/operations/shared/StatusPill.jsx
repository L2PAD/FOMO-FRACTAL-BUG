/**
 * Status Pill - Color-coded status badges
 */

import React from 'react';

export default function StatusPill({ value }) {
  if (!value) return <span className="text-gray-500">—</span>;

  const cls =
    value === 'GOOD' || value === 'OPEN' || value === 'FILLED' || value === 'WIN'
      ? 'bg-green-500/15 text-green-300 border-green-500/30'
      : value === 'WARNING' || value === 'WAITING' || value === 'PARTIAL_FILL' || value === 'BE'
      ? 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30'
      : value === 'CRITICAL' || value === 'LOSS' || value === 'CANCELLED' || value === 'REJECTED'
      ? 'bg-red-500/15 text-red-300 border-red-500/30'
      : 'bg-white/10 text-gray-300 border-white/10';

  return (
    <span className={`inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium ${cls}`}>
      {value}
    </span>
  );
}
