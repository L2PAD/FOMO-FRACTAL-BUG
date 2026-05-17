import React from "react";
import Card from "../Card";
import StatusBadge from "../StatusBadge";
import { Lock, Unlock, Clock, Shield } from "lucide-react";

interface FeatureLockPanelProps {
  featureLock?: {
    locked: boolean;
    reason?: string;
    lockedAt?: string;
    lockedBy?: string;
    ttlMinutes?: number;
    expiresAt?: string;
  };
}

export default function FeatureLockPanel({ featureLock }: FeatureLockPanelProps) {
  const f = featureLock ?? { locked: false };
  const isLocked = f.locked;
  const expiresAt = f.expiresAt ? new Date(f.expiresAt) : null;
  const isExpired = expiresAt && expiresAt < new Date();
  let remainingMinutes = 0;
  if (expiresAt && !isExpired) {
    remainingMinutes = Math.max(0, Math.floor((expiresAt.getTime() - Date.now()) / 60000));
  }

  return (
    <Card title="Блокировка функций (Feature Lock)" right={<StatusBadge level={isLocked ? "WARN" : "OK"} />}>
      <div className="flex items-center gap-3 mb-4 p-3 rounded-lg bg-slate-50">
        {isLocked ? (
          <>
            <Lock className="w-6 h-6 text-amber-600" />
            <div>
              <div className="font-semibold text-amber-700">ЗАБЛОКИРОВАНО</div>
              <div className="text-xs text-slate-500">Мутации модуля запрещены</div>
            </div>
          </>
        ) : (
          <>
            <Unlock className="w-6 h-6 text-emerald-600" />
            <div>
              <div className="font-semibold text-emerald-700">РАЗБЛОКИРОВАНО</div>
              <div className="text-xs text-slate-500">Модуль доступен для изменений</div>
            </div>
          </>
        )}
      </div>
      {isLocked && (
        <div className="space-y-3">
          {f.reason && (
            <div className="flex items-start gap-2">
              <Shield className="w-4 h-4 text-slate-400 mt-0.5" />
              <div>
                <div className="text-xs text-slate-500">Причина блокировки</div>
                <div className="text-sm text-slate-800">{f.reason}</div>
              </div>
            </div>
          )}
          {f.ttlMinutes && (
            <div className="flex items-start gap-2">
              <Clock className="w-4 h-4 text-slate-400 mt-0.5" />
              <div>
                <div className="text-xs text-slate-500">Время жизни (TTL)</div>
                <div className="text-sm text-slate-800">
                  {f.ttlMinutes} мин
                  {remainingMinutes > 0 && <span className="text-amber-600 ml-2">({remainingMinutes} мин осталось)</span>}
                </div>
              </div>
            </div>
          )}
          {expiresAt && (
            <div className="text-xs text-slate-500 mt-2">
              {isExpired ? <span className="text-red-600">Блокировка истекла, ожидается очистка</span> : <span>Истекает: {expiresAt.toLocaleString()}</span>}
            </div>
          )}
          {f.lockedBy && <div className="text-xs text-slate-500">Заблокировано: {f.lockedBy}</div>}
        </div>
      )}
      <div className="mt-4 pt-3">
        <div className="text-xs text-slate-500 mb-2">Блокируемые операции:</div>
        <div className="flex flex-wrap gap-1">
          {['retrain', 'promote', 'rollback', 'config_update', 'baseline_create'].map(op => (
            <span key={op} className="text-xs text-slate-600">{op}</span>
          ))}
        </div>
      </div>
    </Card>
  );
}
