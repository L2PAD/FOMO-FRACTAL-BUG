import React from "react";
import Card from "../Card";
import { SentimentAdminSnapshot } from "../../types/sentimentAdmin.types";
import { FileText, AlertTriangle, CheckCircle, Info, XCircle } from "lucide-react";

interface EvidencePanelProps {
  snapshot: SentimentAdminSnapshot;
}

const severityConfig = {
  INFO: { bg: "bg-slate-100", text: "text-slate-600", icon: Info },
  WARN: { bg: "bg-amber-100", text: "text-amber-700", icon: AlertTriangle },
  CRITICAL: { bg: "bg-red-100", text: "text-red-700", icon: XCircle },
  SUCCESS: { bg: "bg-emerald-100", text: "text-emerald-700", icon: CheckCircle },
};

export default function EvidencePanel({ snapshot }: EvidencePanelProps) {
  const events = snapshot.evidence ?? [];

  return (
    <Card title="Журнал событий (Evidence Log)" right={<span className="text-xs text-slate-500">Последние {events.length} событий</span>}>
      {events.length === 0 ? (
        <div className="text-slate-500 text-sm py-8 text-center flex flex-col items-center gap-2">
          <FileText className="w-8 h-8 text-slate-300" />
          <span>Нет зафиксированных событий</span>
        </div>
      ) : (
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {events.map((ev, idx) => {
            const config = severityConfig[ev.severity as keyof typeof severityConfig] ?? severityConfig.INFO;
            const Icon = config.icon;
            return (
              <div key={idx} className="flex items-start gap-3 p-2 rounded-lg hover:bg-slate-50 transition-colors">
                <div className="text-xs text-slate-400 w-20 flex-shrink-0 pt-0.5">{new Date(ev.timestamp).toLocaleTimeString()}</div>
                <div className={`text-xs font-medium ${config.text} flex items-center gap-1`}>
                  <Icon className="w-3 h-3" />{ev.severity}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-slate-800 truncate">{ev.type}</div>
                  {ev.message && <div className="text-xs text-slate-500 truncate mt-0.5">{ev.message}</div>}
                </div>
                {ev.details && Object.keys(ev.details).length > 0 && (
                  <div className="text-xs text-slate-400 flex-shrink-0">{Object.keys(ev.details).length} полей</div>
                )}
              </div>
            );
          })}
        </div>
      )}
      <div className="mt-3 pt-3 text-xs text-slate-500 text-center">Append-only журнал — авто-обновление каждые 60сек</div>
    </Card>
  );
}
