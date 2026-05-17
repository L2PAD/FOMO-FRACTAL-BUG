import React from 'react';

interface CardProps {
  title: string | React.ReactNode;
  children: React.ReactNode;
  className?: string;
  action?: React.ReactNode;
}

export function Card({ title, children, className = '', action }: CardProps) {
  return (
    <div className={`bg-white rounded-xl border border-slate-200 shadow-sm ${className}`}>
      <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
        {action}
      </div>
      <div className="p-5">
        {children}
      </div>
    </div>
  );
}

export function MiniCard({ label, value, badge }: { label: string; value: React.ReactNode; badge?: React.ReactNode }) {
  return (
    <div className="bg-slate-50 rounded-lg px-4 py-3 border border-slate-100">
      <div className="text-xs text-slate-500 mb-1">{label}</div>
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-slate-800 tabular-nums">{value}</span>
        {badge}
      </div>
    </div>
  );
}
