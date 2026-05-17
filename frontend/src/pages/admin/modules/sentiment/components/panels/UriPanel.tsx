import React from "react";
import Card from "../Card";
import StatusBadge from "../StatusBadge";
import { SentimentAdminSnapshot, ReliabilityLevel } from "../../types/sentimentAdmin.types";
import { Activity, TrendingUp, Shield, Zap } from "lucide-react";

interface UriPanelProps {
  snapshot: SentimentAdminSnapshot;
}

function HealthRow({ name, score, level, icon: Icon }: { 
  name: string; score: number; level: ReliabilityLevel;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  const pct = Math.max(0, Math.min(1, score)) * 100;
  const barColor = {
    OK: "bg-emerald-500", WARN: "bg-amber-500", DEGRADED: "bg-orange-500",
    CRITICAL: "bg-red-500", UNKNOWN: "bg-slate-400",
  }[level] ?? "bg-slate-400";

  return (
    <div className="flex items-center gap-3 py-2">
      {Icon && <Icon className="w-4 h-4 text-slate-400 flex-shrink-0" />}
      <div className="w-32 text-sm text-slate-600">{name}</div>
      <div className="w-14 text-sm text-slate-800 tabular-nums">{Math.round(pct)}%</div>
      <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <StatusBadge level={level} size="sm" />
    </div>
  );
}

export default function UriPanel({ snapshot }: UriPanelProps) {
  const u = snapshot.uri;
  const gaugeRotation = Math.min(180, Math.max(0, u.uriScore * 180));

  return (
    <Card title="Индекс надёжности (URI)" right={<StatusBadge level={u.uriLevel} />}>
      <div className="flex justify-center mb-4">
        <div className="relative w-32 h-16 overflow-hidden">
          <div className="absolute inset-0 rounded-t-full bg-gradient-to-r from-red-200 via-amber-200 to-emerald-200" />
          <div className="absolute bottom-0 left-1/2 w-1 h-14 bg-slate-800 origin-bottom transition-transform duration-700"
            style={{ transform: `translateX(-50%) rotate(${gaugeRotation - 90}deg)` }} />
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 w-3 h-3 rounded-full bg-slate-800" />
        </div>
      </div>
      <div className="text-center mb-4">
        <span className="text-3xl font-bold text-slate-900 tabular-nums">{Math.round(u.uriScore * 100)}%</span>
      </div>
      <div className="space-y-1 pt-3">
        <HealthRow name="Здоровье данных" score={u.components.dataHealth.score} level={u.components.dataHealth.level} icon={Activity} />
        <HealthRow name="Дрейф модели" score={u.components.driftHealth.score} level={u.components.driftHealth.level} icon={TrendingUp} />
        <HealthRow name="Капитал" score={u.components.capitalHealth.score} level={u.components.capitalHealth.level} icon={Zap} />
        <HealthRow name="Калибровка" score={u.components.calibrationHealth.score} level={u.components.calibrationHealth.level} icon={Shield} />
      </div>
      <div className="grid grid-cols-2 gap-2 mt-4 pt-3 text-sm">
        <div className="flex items-center gap-2">
          <span className="text-slate-500">Обучение:</span>
          <span className={u.actions.trainingBlocked ? "text-red-600 font-medium" : "text-emerald-600 font-medium"}>
            {u.actions.trainingBlocked ? "ЗАБЛОК." : "ОК"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-500">Промоция:</span>
          <span className={u.actions.promotionBlocked ? "text-red-600 font-medium" : "text-emerald-600 font-medium"}>
            {u.actions.promotionBlocked ? "ЗАБЛОК." : "ОК"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-500">Воркеры:</span>
          <span className={u.actions.workersBlocked ? "text-red-600 font-medium" : "text-emerald-600 font-medium"}>
            {u.actions.workersBlocked ? "ЗАБЛОК." : "ОК"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-500">Безоп. режим:</span>
          <span className={u.actions.safeMode ? "text-amber-600 font-medium" : "text-slate-600"}>
            {u.actions.safeMode ? "ВКЛ" : "ВЫКЛ"}
          </span>
        </div>
      </div>
    </Card>
  );
}
