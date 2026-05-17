/**
 * WS Connection Badge
 * Sprint WS-3: Shows connection status (LIVE vs POLLING)
 */

import React from 'react';

export function WsConnectionBadge({ isConnected }) {
  if (isConnected) {
    return (
      <span 
        className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
        data-testid="ws-badge-live"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        LIVE
      </span>
    );
  }
  
  return (
    <span 
      className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium bg-yellow-500/10 text-yellow-400 border border-yellow-500/20"
      data-testid="ws-badge-polling"
    >
      <span className="w-1.5 h-1.5 rounded-full bg-yellow-400" />
      POLLING
    </span>
  );
}
