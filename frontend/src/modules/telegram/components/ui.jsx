/**
 * UI Primitives (Card, Stat, Badge)
 */
import React from 'react';

export function Card({ title, subtitle, children, className = '' }) {
  return (
    <div className={`bg-white border border-gray-200 rounded-2xl p-4 ${className}`}>
      {title && (
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-black text-gray-900">{title}</div>
          {subtitle && <span className="text-xs text-gray-400">{subtitle}</span>}
        </div>
      )}
      {children}
    </div>
  );
}

export function Stat({ label, value, sub }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="text-xs text-gray-500 font-semibold uppercase tracking-wide">{label}</div>
      <div className="text-xl font-black text-gray-900">{value ?? '—'}</div>
      {sub && <div className="text-xs text-gray-500">{sub}</div>}
    </div>
  );
}

export function Badge({ text, color = 'gray' }) {
  const colors = {
    gray: 'bg-gray-100 text-gray-700 border-gray-200',
    teal: 'bg-teal-50 text-teal-700 border-teal-200',
    red: 'bg-red-50 text-red-600 border-red-200',
    green: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  };

  return (
    <span className={`inline-flex items-center h-6 px-2.5 rounded-full text-xs font-bold border ${colors[color] || colors.gray}`}>
      {text}
    </span>
  );
}

export function MetricRow({ label, value }) {
  return (
    <div className="flex justify-between items-center text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="font-semibold text-gray-900">{value ?? '—'}</span>
    </div>
  );
}
