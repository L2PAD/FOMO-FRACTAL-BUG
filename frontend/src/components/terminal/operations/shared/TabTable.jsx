/**
 * Tab Table - Unified table rendering with binding support
 */

import React from 'react';

export default function TabTable({ columns, rows }) {
  return (
    <div className="overflow-auto">
      <table className="w-full text-sm text-white">
        <thead className="text-left text-xs text-gray-400">
          <tr>
            {columns.map((col) => (
              <th key={col.key} className="pb-3 pr-4 font-medium">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {rows.map((row, idx) => (
            <tr
              key={row.id || idx}
              className={`border-t border-white/5 hover:bg-white/5 transition-colors cursor-pointer ${row.className || ''}`}
              onMouseEnter={row.onMouseEnter}
              onMouseLeave={row.onMouseLeave}
              onClick={row.onClick}
            >
              {columns.map((col) => (
                <td key={col.key} className="py-3 pr-4 align-top">
                  {col.render ? col.render(row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
