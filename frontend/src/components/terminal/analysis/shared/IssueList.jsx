/**
 * IssueList - Validation issues list
 */

import React from 'react';

export function IssueList({ issues }) {
  return (
    <div>
      <div className="mb-2 text-xs uppercase tracking-wide text-gray-400">Issues</div>
      <div className="space-y-2">
        {issues?.length ? (
          issues.map((x, i) => (
            <div
              key={`${x.type}-${i}`}
              className={`rounded-lg px-3 py-2 text-xs ${
                x.severity === 'critical'
                  ? 'bg-red-500/10 text-red-300 border border-red-500/20'
                  : x.severity === 'warning'
                  ? 'bg-yellow-500/10 text-yellow-300 border border-yellow-500/20'
                  : 'bg-white/5 text-gray-300 border border-white/10'
              }`}
            >
              <div className="font-medium">{x.type}</div>
              <div className="mt-0.5">{x.message}</div>
            </div>
          ))
        ) : (
          <span className="text-xs text-gray-500">No validation issues</span>
        )}
      </div>
    </div>
  );
}
