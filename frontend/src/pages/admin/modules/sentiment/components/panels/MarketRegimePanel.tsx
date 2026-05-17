import React from "react";
import Card from "../Card";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface MarketRegimePanelProps {
  regime?: string;
  trendStrength?: number;
}

export default function MarketRegimePanel({ regime = "UNKNOWN", trendStrength = 0 }: MarketRegimePanelProps) {
  const getRegimeColor = (r: string) => {
    switch (r) { case "BULL": return "text-emerald-600"; case "BEAR": return "text-red-600"; case "SIDEWAYS": return "text-amber-600"; default: return "text-slate-500"; }
  };
  const getRegimeIcon = (r: string) => {
    switch (r) { case "BULL": return <TrendingUp className="w-5 h-5 text-emerald-500" />; case "BEAR": return <TrendingDown className="w-5 h-5 text-red-500" />; default: return <Minus className="w-5 h-5 text-slate-400" />; }
  };
  const strengthPct = Math.round(trendStrength * 100);

  return (
    <Card title="Рыночный режим">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {getRegimeIcon(regime)}
          <div>
            <div className={`text-xl font-bold ${getRegimeColor(regime)}`}>{regime}</div>
            <div className="text-xs text-slate-500">Текущий режим</div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xl font-bold text-slate-800">{strengthPct}%</div>
          <div className="text-xs text-slate-500">Сила тренда</div>
        </div>
      </div>
      <div className="mt-4">
        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
          <div className={`h-full transition-all ${regime === "BULL" ? "bg-emerald-500" : regime === "BEAR" ? "bg-red-500" : "bg-slate-400"}`} style={{ width: `${strengthPct}%` }} />
        </div>
      </div>
    </Card>
  );
}
