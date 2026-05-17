/**
 * PanelShell - Wrapper for analysis panels
 */

import React from 'react';

export function PanelShell({ title, children }) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#11161D] p-4">
      <div className="mb-4 text-sm font-semibold text-white">{title}</div>
      <div className="space-y-3 text-sm text-white">{children}</div>
    </div>
  );
}
