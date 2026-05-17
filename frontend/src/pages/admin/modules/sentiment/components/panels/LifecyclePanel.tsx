import React from "react";
import Card from "../Card";
import { SentimentAdminSnapshot } from "../../types/sentimentAdmin.types";
import { Cpu, GitCompare, Clock, RotateCcw } from "lucide-react";

interface LifecyclePanelProps {
  snapshot: SentimentAdminSnapshot;
}

function Row({ label, value, color }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <div className="flex justify-between items-center py-2">
      <span className="text-slate-600 text-sm">{label}</span>
      <span className={`text-sm font-medium ${color ?? "text-slate-800"}`}>{value}</span>
    </div>
  );
}

function fmtPct(x?: number) {
  if (x === undefined || x === null) return "—";
  return (x * 100).toFixed(2) + "%";
}

export default function LifecyclePanel({ snapshot }: LifecyclePanelProps) {
  const l = snapshot.lifecycle;
  if (!l) {
    return <Card title="Жизненный цикл и Shadow"><div className="text-slate-500 text-sm py-4 text-center">Нет данных</div></Card>;
  }
  const isML = l.mode === "ML";

  return (
    <Card 
      title="Жизненный цикл и Shadow" 
      right={
        <span className={`text-sm font-semibold ${
          isML ? "text-blue-600" : "text-slate-600"
        }`}>{l.mode}</span>
      }
    >
      <div className="space-y-1 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Cpu className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-medium text-slate-700">Движок решений</span>
        </div>
        <Row label="Активный режим" value={l.mode} color={isML ? "text-blue-600" : "text-slate-600"} />
        <Row label="Shadow-решения" value={l.shadowDecisions ?? 0} />
      </div>
      <div className="space-y-1 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <GitCompare className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-medium text-slate-700">Дельта (ML − RULE)</span>
        </div>
        <Row label="Edge Delta" value={fmtPct(l.edgeDelta)} color={l.edgeDelta > 0.02 ? "text-emerald-600" : l.edgeDelta < -0.02 ? "text-red-600" : "text-slate-600"} />
        <div className="text-xs text-slate-500 mt-1">Промоция: &gt; 2% edge за 3 окна подряд</div>
      </div>
      <div className="space-y-1 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Clock className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-medium text-slate-700">Кулдаун промоции</span>
        </div>
        <Row label="Осталось дней" value={`${l.cooldownRemainingDays ?? 0}д`} color={l.cooldownRemainingDays > 0 ? "text-amber-600" : "text-slate-600"} />
        {l.lastPromotion && <Row label="Последняя промоция" value={new Date(l.lastPromotion).toLocaleDateString()} />}
      </div>
      <div className="space-y-1">
        <div className="flex items-center gap-2 mb-3">
          <RotateCcw className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-medium text-slate-700">Статус отката</span>
        </div>
        {l.lastRollback ? (
          <Row label="Последний откат" value={new Date(l.lastRollback).toLocaleDateString()} color="text-red-600" />
        ) : (
          <div className="text-sm text-slate-500 py-2">Откатов не зафиксировано</div>
        )}
      </div>
    </Card>
  );
}
