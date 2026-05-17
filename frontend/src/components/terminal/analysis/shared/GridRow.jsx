/**
 * GridRow - Key-value row for panels
 */

import React from 'react';

export function GridRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="text-gray-400">{label}</div>
      <div className="text-right text-white">{value ?? '—'}</div>
    </div>
  );
}
