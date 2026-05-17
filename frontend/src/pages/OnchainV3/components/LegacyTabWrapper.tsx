/**
 * Legacy Tab Wrapper
 * ==================
 * 
 * P0.8: Wraps v1 legacy pages for embedding in OnchainV3
 * Ensures no layout/header/sidebar pollution
 */

import React from 'react';

interface LegacyTabWrapperProps {
  children: React.ReactNode;
  title?: string;
}

export default function LegacyTabWrapper({ children, title }: LegacyTabWrapperProps) {
  return (
    <div 
      className="w-full flex flex-col"
      style={{ minHeight: '600px' }}
      data-testid="legacy-tab-wrapper"
    >
      {title && (
        <div className="mb-4 pb-3">
          <h2 className="text-lg font-bold text-gray-900">{title}</h2>
          <p className="text-xs text-gray-500 mt-1">Legacy v1 module (embedded)</p>
        </div>
      )}
      <div className="flex-1">
        {children}
      </div>
    </div>
  );
}
