import { useEffect, useState } from "react";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function SummaryTile({ label, value }) {
  return (
    <div className="rounded-lg bg-gray-50 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-gray-900">{value}</div>
    </div>
  );
}

export default function ExecutionPanel({ lang = 'ru' }) {
  const [data, setData] = useState(null);

  const t = (ru, en) => (lang === 'ru' ? ru : en);

  const load = async () => {
    try {
      const res = await fetch(`${API_URL}/api/trading/execution-quality`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      console.error("ExecutionPanel load error", e);
    }
  };

  useEffect(() => {
    load();
    const i = setInterval(load, 5000);
    return () => clearInterval(i);
  }, []);

  if (!data) return null;

  const hasOrders = data.orders && data.orders.length > 0;

  return (
    <div className="bg-white rounded-xl p-4">
      <div className="mb-4">
        <div className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-900">
          {t('КАЧЕСТВО ИСПОЛНЕНИЯ', 'EXECUTION QUALITY')}
        </div>
        <div className="mt-1 text-sm text-gray-600">{t('Метрики исполнения', 'Execution metrics')}</div>
      </div>

      <div className="mb-4 grid grid-cols-3 gap-2">
        <SummaryTile label={t('КАЧЕСТВО', 'QUALITY')} value={Number(data.avg_quality || 0).toFixed(1)} />
        <SummaryTile label={t('SLIPPAGE', 'SLIPPAGE')} value={`${Number(data.avg_slippage || 0).toFixed(2)} bps`} />
        <SummaryTile label={t('ЛАТЕНТНОСТЬ', 'LATENCY')} value={`${Number(data.avg_latency || 0).toFixed(0)} ms`} />
      </div>

      <div className="space-y-2" data-testid="execution-table">
        {hasOrders ? (
          (data.orders || []).slice(0, 5).map((o, i) => (
            <div key={`${o.symbol}-${i}`} className="rounded-lg bg-gray-50 px-3 py-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-gray-900">{o.symbol}</span>
                <span className="text-gray-900">Q {Number(o.quality || 0).toFixed(1)}</span>
              </div>
              <div className="mt-1 text-gray-500">
                {Number(o.slippage || 0).toFixed(2)} bps · {Number(o.latency || 0).toFixed(0)} ms
              </div>
            </div>
          ))
        ) : (
          <div className="text-center py-8 text-xs text-gray-500">
            System active · waiting for executions
          </div>
        )}
      </div>
    </div>
  );
}
