import React from "react";
import Card from "../Card";
import { SentimentAdminSnapshot } from "../../types/sentimentAdmin.types";
import { Shield, AlertTriangle, CheckCircle, XCircle, Scale, TrendingDown } from "lucide-react";

interface GuardActionsPanelProps {
  snapshot: SentimentAdminSnapshot;
}

function ActionRow({ label, value, isBlocked, icon: Icon }: { 
  label: string; value: string; isBlocked?: boolean;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="flex items-center justify-between py-2 last:border-0">
      <div className="flex items-center gap-2 text-sm text-slate-600">
        {Icon && <Icon className="w-4 h-4 text-slate-400" />}
        {label}
      </div>
      <div className="flex items-center gap-2">
        {isBlocked !== undefined && (
          isBlocked ? <XCircle className="w-4 h-4 text-red-500" /> : <CheckCircle className="w-4 h-4 text-emerald-500" />
        )}
        <span className={`text-sm font-medium ${isBlocked ? "text-red-600" : "text-slate-800"}`}>{value}</span>
      </div>
    </div>
  );
}

export default function GuardActionsPanel({ snapshot }: GuardActionsPanelProps) {
  const a = snapshot.uri.actions;
  const reasons = snapshot.parserHealth?.reasons ?? [];

  return (
    <Card 
      title="Защитные действия (Guard Actions)"
      right={
        a.safeMode ? (
          <span className="flex items-center gap-1.5 text-xs font-semibold text-amber-600">
            <Shield className="w-3.5 h-3.5" /> БЕЗОП. РЕЖИМ
          </span>
        ) : (
          <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600">
            <CheckCircle className="w-3.5 h-3.5" /> НОРМА
          </span>
        )
      }
    >
      <div className="space-y-1">
        <ActionRow label="Обучение" value={a.trainingBlocked ? "ЗАБЛОК." : "ОК"} isBlocked={a.trainingBlocked} />
        <ActionRow label="Промоция" value={a.promotionBlocked ? "ЗАБЛОК." : "ОК"} isBlocked={a.promotionBlocked} />
        <ActionRow label="Воркеры" value={a.workersBlocked ? "ЗАБЛОК." : "ОК"} isBlocked={a.workersBlocked} />
      </div>
      <div className="mt-4 pt-3">
        <div className="text-xs font-medium text-slate-500 mb-2 uppercase tracking-wide">Множители</div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
            <div className="flex items-center gap-1.5 text-xs text-slate-600">
              <Scale className="w-3.5 h-3.5" /> Уверенность ×
            </div>
            <span className={`text-sm font-medium ${a.confidenceMultiplier < 1 ? "text-amber-600" : "text-slate-800"}`}>
              {a.confidenceMultiplier.toFixed(2)}
            </span>
          </div>
          <div className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
            <div className="flex items-center gap-1.5 text-xs text-slate-600">
              <TrendingDown className="w-3.5 h-3.5" /> Размер ×
            </div>
            <span className={`text-sm font-medium ${a.sizeMultiplier < 1 ? "text-amber-600" : "text-slate-800"}`}>
              {a.sizeMultiplier.toFixed(2)}
            </span>
          </div>
        </div>
      </div>
      {a.safeMode && (
        <div className="mt-4 pt-3">
          <div className="text-xs font-medium text-slate-500 mb-2 uppercase tracking-wide">Причина безоп. режима</div>
          <div className="p-3 bg-amber-50 rounded-lg">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-amber-800">
                {a.safeModeReason ?? "Низкое здоровье данных или критическое состояние системы"}
              </div>
            </div>
          </div>
        </div>
      )}
      {reasons.length > 0 && (
        <div className="mt-4 pt-3">
          <div className="text-xs font-medium text-slate-500 mb-2 uppercase tracking-wide">Активные причины</div>
          <div className="flex flex-wrap gap-1.5">
            {reasons.map((reason, idx) => (
              <span key={idx} className={`text-xs font-medium ${
                reason.includes("CRITICAL") || reason.includes("SAFE") ? "text-red-600" :
                reason.includes("WARN") || reason.includes("MISSING") ? "text-amber-600" :
                "text-slate-600"
              }`}>{reason}</span>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
