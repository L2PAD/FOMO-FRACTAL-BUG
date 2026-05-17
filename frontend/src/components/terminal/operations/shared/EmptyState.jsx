/**
 * Empty State - For empty tabs
 */

import React from 'react';

export default function EmptyState({ title = 'No data' }) {
  return (
    <div className="rounded-xl border border-dashed border-white/10 bg-[#11161D] p-6 text-center text-sm text-gray-400">
      {title}
    </div>
  );
}
