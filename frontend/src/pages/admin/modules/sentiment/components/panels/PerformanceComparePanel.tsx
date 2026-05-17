import React from "react";
import Card from "../Card";

interface PerformanceComparePanelProps {
  mlEquity?: number[];
  ruleEquity?: number[];
  rollingHitRate?: number;
  rollingSharpe?: number;
}

function Sparkline({ data, color = "#6366f1", height = 48 }: { data: number[]; color?: string; height?: number }) {
  if (!data?.length) return null;
  const width = 200;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data.map((v, i) => `${(i / (data.length - 1)) * width},${height - ((v - min) / range) * height}`).join(' ');
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <polyline fill="none" stroke={color} strokeWidth="2" points={points} />
    </svg>
  );
}

export default function PerformanceComparePanel({ mlEquity = [], ruleEquity = [], rollingHitRate = 0, rollingSharpe = 0 }: PerformanceComparePanelProps) {
  return (
    <Card 
      title="ML vs Правила — сравнение"
      right={
        <div className="flex gap-3 text-xs">
          <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-indigo-500" /> ML</span>
          <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-slate-400" /> Правила</span>
        </div>
      }
    >
      <div className="h-16 relative mb-4">
        <div className="absolute inset-0"><Sparkline data={mlEquity} color="#6366f1" height={64} /></div>
        <div className="absolute inset-0 opacity-50"><Sparkline data={ruleEquity} color="#9ca3af" height={64} /></div>
      </div>
      <div className="flex gap-6 text-sm pt-3">
        <div>
          <span className="text-slate-500">Hit Rate:</span>
          <span className={`ml-2 font-medium ${rollingHitRate >= 0.5 ? 'text-emerald-600' : 'text-red-600'}`}>{Math.round(rollingHitRate * 100)}%</span>
        </div>
        <div>
          <span className="text-slate-500">Шарп:</span>
          <span className={`ml-2 font-medium ${rollingSharpe >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{rollingSharpe.toFixed(2)}</span>
        </div>
      </div>
    </Card>
  );
}
