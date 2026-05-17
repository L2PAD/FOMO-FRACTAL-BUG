import React, { useState } from "react";
import Card from "../Card";
import { Play, RefreshCw, Loader2, CheckCircle, XCircle } from "lucide-react";

const API_URL = process.env.REACT_APP_BACKEND_URL || "";

interface ManualActionsPanelProps {
  moduleKey?: string;
}

type ActionStatus = "idle" | "loading" | "success" | "error";

const ACTIONS = [
  { label: "Перезапустить проверку дрейфта", endpoint: "/api/admin/sentiment-ml/drift/stabilizer/run", description: "Пересчитать PSI и обновить стабилизированный статус" },
  { label: "Перезапустить калибровку", endpoint: "/api/admin/sentiment-ml/calibration/run", description: "Обновить ECE и постериоры бакетов" },
  { label: "Пересчитать окно капитала", endpoint: "/api/admin/sentiment-ml/capital/window/recalc", description: "Обновить метрики за скользящие 30Д" },
  { label: "Принудительный сброс Evidence", endpoint: "/api/admin/sentiment-ml/evidence/flush", description: "Сохранить ожидающие события" },
];

export default function ManualActionsPanel({ moduleKey = "sentiment" }: ManualActionsPanelProps) {
  const [statuses, setStatuses] = useState<Record<string, ActionStatus>>({});

  const runAction = async (endpoint: string) => {
    setStatuses(s => ({ ...s, [endpoint]: "loading" }));
    try {
      const res = await fetch(`${API_URL}${endpoint}`, { method: "POST", headers: { "Content-Type": "application/json" } });
      setStatuses(s => ({ ...s, [endpoint]: res.ok ? "success" : "error" }));
      setTimeout(() => setStatuses(s => ({ ...s, [endpoint]: "idle" })), res.ok ? 2000 : 3000);
    } catch {
      setStatuses(s => ({ ...s, [endpoint]: "error" }));
      setTimeout(() => setStatuses(s => ({ ...s, [endpoint]: "idle" })), 3000);
    }
  };

  const getStatusIcon = (status: ActionStatus) => {
    switch (status) {
      case "loading": return <Loader2 className="w-4 h-4 animate-spin text-blue-500" />;
      case "success": return <CheckCircle className="w-4 h-4 text-emerald-500" />;
      case "error": return <XCircle className="w-4 h-4 text-red-500" />;
      default: return <Play className="w-4 h-4 text-slate-400" />;
    }
  };

  return (
    <Card title="Ручное управление" right={<span className="text-xs text-slate-500 flex items-center gap-1"><RefreshCw className="w-3 h-3" />Только админ</span>}>
      <div className="space-y-2">
        {ACTIONS.map((action) => {
          const status = statuses[action.endpoint] ?? "idle";
          return (
            <button key={action.endpoint} onClick={() => runAction(action.endpoint)} disabled={status === "loading"}
              className={`w-full flex items-center gap-3 p-3 rounded-lg text-left transition-all duration-150 ${
                status === "loading" ? "bg-slate-50 cursor-wait" : "bg-white hover:bg-slate-50 cursor-pointer"
              }`}>
              <div className="flex-shrink-0">{getStatusIcon(status)}</div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-slate-800">{action.label}</div>
                <div className="text-xs text-slate-500 truncate">{action.description}</div>
              </div>
            </button>
          );
        })}
      </div>
      <div className="mt-3 pt-3 text-xs text-slate-400 text-center">Действия записываются в Evidence Trail</div>
    </Card>
  );
}
