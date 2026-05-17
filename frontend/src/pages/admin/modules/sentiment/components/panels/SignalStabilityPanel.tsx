import React from "react";
import Card from "../Card";

interface SignalStabilityPanelProps {
  uriAdjustmentsPct?: number;
  safeModePct?: number;
  calibrationAdjustmentsPct?: number;
  lowDataPct?: number;
}

function ProgressBar({ label, value, color = "bg-indigo-500" }: { label: string; value: number; color?: string }) {
  const pct = Math.round(value * 100);
  return (
    <div className="mb-3 last:mb-0">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-slate-600">{label}</span>
        <span className="text-slate-800 font-medium">{pct}%</span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-2 rounded-full transition-all ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
    </div>
  );
}

export default function SignalStabilityPanel({ uriAdjustmentsPct = 0, safeModePct = 0, calibrationAdjustmentsPct = 0, lowDataPct = 0 }: SignalStabilityPanelProps) {
  return (
    <Card title="Стабильность сигнала (30Д)">
      <ProgressBar label="Коррекции URI" value={uriAdjustmentsPct} color="bg-indigo-500" />
      <ProgressBar label="Срабатывания безоп. режима" value={safeModePct} color="bg-amber-500" />
      <ProgressBar label="Изменения калибровки" value={calibrationAdjustmentsPct} color="bg-blue-500" />
      <ProgressBar label="Инстансы с нехваткой данных" value={lowDataPct} color="bg-slate-400" />
    </Card>
  );
}
