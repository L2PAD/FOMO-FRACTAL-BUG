/**
 * TagList - List of tags/labels
 */

import React from 'react';

export function TagList({ title, items, empty }) {
  return (
    <div>
      <div className="mb-2 text-xs uppercase tracking-wide text-gray-400">{title}</div>
      <div className="flex flex-wrap gap-2">
        {items?.length ? (
          items.map((x, i) => (
            <span
              key={i}
              className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-xs text-gray-300"
            >
              {x}
            </span>
          ))
        ) : (
          <span className="text-xs text-gray-500">{empty}</span>
        )}
      </div>
    </div>
  );
}
