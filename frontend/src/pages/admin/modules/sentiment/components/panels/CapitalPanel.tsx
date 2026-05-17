import React from "react";
import Card from "../Card";
import StatusBadge from "../StatusBadge";
import MiniSparkline from "../common/MiniSparkline";
import { SentimentAdminSnapshot, ReliabilityLevel } from "../../types/sentimentAdmin.types";
import { TrendingDown, BarChart3, Target } from "lucide-react";

interface CapitalPanelProps {
  snapshot: SentimentAdminSnapshot;
}

function fmtPct(x?: number, decimals = 2) {
  if (x === undefined || x === null) return "—";
  return (x * 100).toFixed(decimals) + "%";
}

function Row({ label, value, color }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <div className="flex justify-between items-center py-2">
      <span className="text-slate-600 text-sm">{label}</span>
      <span className={`text-sm font-medium ${color ?? "text-slate-800"}`}>{value}</span>
    </div>
  );
}

export default function CapitalPanel({ snapshot }: CapitalPanelProps) {
  const c = snapshot.capital;
  const gates = snapshot.capitalGates;
  if (!c) {
    return <Card title="Здоровье капитала"><div className="text-slate-500 text-sm py-4 text-center">Нет данных по капиталу</div></Card>;
  }
  const expectancyOk = c.expectancy >= 0;
  const ddOk = c.maxDD < 0.15;
  const sharpeOk = c.sharpe > 0.1;
  const healthLevel: ReliabilityLevel = (expectancyOk && ddOk && sharpeOk) ? "OK" : (!expectancyOk || c.maxDD > 0.20) ? "CRITICAL" : "WARN";

  return (
    <Card title="Здоровье капитала (30Д)" right={<StatusBadge level={healthLevel} />}>
      {c.equityHistory && c.equityHistory.length > 0 && (
        <div className="mb-4 p-2 bg-slate-50 rounded-lg">
          <div className="text-xs text-slate-500 mb-1">Кривая капитала (30д)</div>
          <MiniSparkline values={c.equityHistory} color={c.expectancy >= 0 ? "rgb(16, 185, 129)" : "rgb(239, 68, 68)"} height={36} showDots />
        </div>
      )}
      <div className="space-y-1 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <BarChart3 className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-medium text-slate-700">Производительность</span>
        </div>
        <Row label="Сделки" value={c.trades ?? 0} />
        <Row label="Win Rate" value={fmtPct(c.winRate, 1)} />
        <Row label="Ожидание (Expectancy)" value={fmtPct(c.expectancy)} color={c.expectancy >= 0 ? "text-emerald-600" : "text-red-600"} />
      </div>
      <div className="space-y-1 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <TrendingDown className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-medium text-slate-700">Риск</span>
        </div>
        <Row label="Макс. просадка (Max DD)" value={fmtPct(c.maxDD, 1)} color={c.maxDD > 0.15 ? "text-red-600" : c.maxDD > 0.10 ? "text-amber-600" : "text-slate-800"} />
        <Row label="Шарп (Sharpe)" value={c.sharpe?.toFixed(3) ?? "—"} color={c.sharpe < 0 ? "text-red-600" : c.sharpe > 0.5 ? "text-emerald-600" : "text-slate-800"} />
        <Row label="Капитал (Equity)" value={c.equity?.toFixed(4) ?? "1.0000"} />
      </div>
      {gates && (
        <div className="space-y-1">
          <div className="flex items-center gap-2 mb-3">
            <Target className="w-4 h-4 text-slate-400" />
            <span className="text-sm font-medium text-slate-700">Гейты жизн. цикла</span>
          </div>
          <Row label="Промоция возможна" value={gates.promotionEligible ? "ДА" : "НЕТ"} color={gates.promotionEligible ? "text-emerald-600" : "text-slate-500"} />
          <Row label="Откат сработал" value={gates.rollbackTriggered ? "ДА" : "НЕТ"} color={gates.rollbackTriggered ? "text-red-600" : "text-slate-500"} />
          {gates.promotionLockActive && (
            <Row label="Блокировка до" value={gates.promotionLockUntil ? new Date(gates.promotionLockUntil).toLocaleDateString() : "—"} color="text-amber-600" />
          )}
        </div>
      )}
      <div className="mt-4 pt-3 text-xs text-slate-500">
        Гейты: Exp &gt; 0%, MaxDD &lt; 15%, Sharpe &gt; 0.10, URI &gt; 60%
      </div>
    </Card>
  );
}
