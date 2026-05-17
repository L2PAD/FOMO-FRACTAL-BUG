import React from "react";
import Card from "../Card";
import StatusBadge from "../StatusBadge";
import MiniSparkline from "../common/MiniSparkline";
import { SentimentAdminSnapshot, ReliabilityLevel } from "../../types/sentimentAdmin.types";
import { TrendingUp, GitBranch, Clock } from "lucide-react";

interface DriftPanelProps {
  snapshot: SentimentAdminSnapshot;
}

function Row({ label, value, highlight }: { label: string; value: React.ReactNode; highlight?: boolean }) {
  return (
    <div className="flex justify-between items-center py-2">
      <span className="text-slate-600 text-sm">{label}</span>
      <span className={`text-sm ${highlight ? "font-semibold text-slate-900" : "text-slate-800"}`}>{value}</span>
    </div>
  );
}

export default function DriftPanel({ snapshot }: DriftPanelProps) {
  const d = snapshot.drift;
  if (!d) {
    return <Card title="Стабилизация дрейфа (Drift)"><div className="text-slate-500 text-sm py-4 text-center">Нет данных по дрейфу</div></Card>;
  }
  const psiStatus = d.status as ReliabilityLevel;

  return (
    <Card title="Стабилизация дрейфа (PSI)" right={<StatusBadge level={psiStatus} />}>
      <div className="space-y-1 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-medium text-slate-700">Метрики PSI</span>
        </div>
        {d.psiHistory && d.psiHistory.length > 0 && (
          <div className="mb-3 p-2 bg-slate-50 rounded-lg">
            <div className="text-xs text-slate-500 mb-1">Тренд PSI (30д)</div>
            <MiniSparkline values={d.psiHistory} color="rgb(59, 130, 246)" height={36} showDots />
          </div>
        )}
        <Row label="Raw PSI" value={d.psiRaw?.toFixed(4) ?? "—"} />
        <Row label="EMA PSI" value={d.psiEma?.toFixed(4) ?? "—"} highlight />
        <Row label="EMA Alpha" value="0.2" />
      </div>
      <div className="space-y-1 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <GitBranch className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-medium text-slate-700">Базовая линия</span>
        </div>
        <Row label="Версия" value={d.baselineVersion ?? "—"} highlight />
        <Row label="Создана" value={d.baselineCreatedAt ? new Date(d.baselineCreatedAt).toLocaleDateString() : "—"} />
        <Row label="Возраст (дней)" value={d.baselineAge ?? "—"} />
      </div>
      <div className="space-y-1">
        <div className="flex items-center gap-2 mb-3">
          <Clock className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-medium text-slate-700">Серия превышений</span>
        </div>
        <Row label="Текущая серия" value={d.streakCount ?? 0} highlight />
        <div className="text-xs text-slate-500 mt-2">
          Пороги: WARN &gt; 3, DEGRADED &gt; 2, CRITICAL &gt; 1
        </div>
      </div>
      <div className="mt-4 pt-3 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-slate-600">Стабилизированный статус:</span>
          <span className={`font-semibold ${
            psiStatus === "OK" ? "text-emerald-600" : psiStatus === "WARN" ? "text-amber-600" :
            psiStatus === "DEGRADED" ? "text-orange-600" : "text-red-600"
          }`}>{psiStatus}</span>
        </div>
      </div>
    </Card>
  );
}
