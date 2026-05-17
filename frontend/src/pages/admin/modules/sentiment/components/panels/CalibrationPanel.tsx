import React from "react";
import Card from "../Card";
import StatusBadge from "../StatusBadge";
import { SentimentAdminSnapshot, ReliabilityLevel } from "../../types/sentimentAdmin.types";
import { Target, BarChart } from "lucide-react";

interface CalibrationPanelProps {
  snapshot: SentimentAdminSnapshot;
}

function fmtPct(x?: number) {
  if (x === undefined || x === null) return "—";
  return (x * 100).toFixed(1) + "%";
}

export default function CalibrationPanel({ snapshot }: CalibrationPanelProps) {
  const c = snapshot.calibration;
  if (!c) {
    return <Card title="Калибровка (ECE)"><div className="text-slate-500 text-sm py-4 text-center">Нет данных по калибровке</div></Card>;
  }
  const eceLevel: ReliabilityLevel = c.ece < 0.05 ? "OK" : c.ece < 0.10 ? "WARN" : c.ece < 0.15 ? "DEGRADED" : "CRITICAL";

  return (
    <Card title="Калибровка (Beta-Binomial)" right={<StatusBadge level={c.status ?? eceLevel} />}>
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Target className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-medium text-slate-700">Ожидаемая ошибка калибровки (ECE)</span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className={`text-3xl font-bold tabular-nums ${
            c.ece < 0.05 ? "text-emerald-600" : c.ece < 0.10 ? "text-amber-600" : "text-red-600"
          }`}>{fmtPct(c.ece)}</span>
          <span className="text-sm text-slate-500">ECE</span>
        </div>
        <div className="text-xs text-slate-500 mt-1">Цель: &lt; 5% (хорошая калибровка)</div>
      </div>
      {c.buckets && c.buckets.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <BarChart className="w-4 h-4 text-slate-400" />
            <span className="text-sm font-medium text-slate-700">Бакеты уверенности</span>
          </div>
          <div className="space-y-2">
            {c.buckets.map((b, idx) => {
              const range = `${(b.bucketMin * 100).toFixed(0)}-${(b.bucketMax * 100).toFixed(0)}%`;
              const barWidth = Math.min(100, b.posteriorMean * 100);
              const isCalibrated = Math.abs(b.posteriorMean - ((b.bucketMin + b.bucketMax) / 2)) < 0.10;
              return (
                <div key={idx} className="text-xs">
                  <div className="flex justify-between mb-1">
                    <span className="text-slate-600">{range}</span>
                    <span className="text-slate-500">n={b.total}, побед={b.wins}</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full transition-all ${isCalibrated ? "bg-emerald-400" : "bg-amber-400"}`} style={{ width: `${barWidth}%` }} />
                  </div>
                  <div className="text-right text-slate-500 mt-0.5">постериор: {fmtPct(b.posteriorMean)}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
      <div className="mt-4 pt-3 text-xs text-slate-500">Приор: Beta(2,2) — обновляется при каждом решении</div>
    </Card>
  );
}
