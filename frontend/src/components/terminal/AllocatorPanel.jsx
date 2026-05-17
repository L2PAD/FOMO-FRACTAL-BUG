import { useEffect, useState } from "react";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function Metric({ label, value }) {
  return (
    <div className="rounded-lg bg-gray-50 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-gray-900">{value}</div>
    </div>
  );
}

function RiskBar({ value }) {
  const width = Math.max(0, Math.min(value * 100, 100));
  return (
    <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-gray-100">
      <div
        className="h-2 rounded-full bg-gray-900 transition-all"
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

export default function AllocatorPanel({ lang = 'ru' }) {
  const [data, setData] = useState(null);

  const t = (ru, en) => (lang === 'ru' ? ru : en);

  const load = async () => {
    try {
      const res = await fetch(`${API_URL}/api/strategy/allocator-v3`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      console.error("AllocatorPanel load error", e);
    }
  };

  useEffect(() => {
    load();
    const i = setInterval(load, 3000);
    return () => clearInterval(i);
  }, []);

  const decisions = data?.decisions || [];
  const meta = data?.allocator_meta || {};

  return (
    <div className="bg-white rounded-xl p-4">
      <div className="mb-4">
        <div className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-900">
          {t('АЛЛОКАТОР V3', 'ALLOCATOR V3')}
        </div>
        <div className="mt-1 text-sm text-gray-600">
          {t('Распределение капитала', 'Capital allocation')}
        </div>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2">
        <Metric label={t('РЕЖИМ', 'REGIME')} value={String(meta.regime || "N/A").toUpperCase()} />
        <Metric label={t('СИГНАЛОВ', 'SIGNALS')} value={meta.signals_out ?? 0} />
      </div>

      {decisions.length === 0 ? (
        <div className="rounded-xl bg-gray-50 px-4 py-6 text-sm text-gray-500">
          {t('Нет решений', 'No decisions')}
        </div>
      ) : (
        <div className="space-y-3">
          {decisions.map((d, i) => (
            <div key={`${d.symbol}-${i}`} className="rounded-xl bg-gray-50 px-3 py-3" data-testid={`allocator-strategy-row-${d.symbol}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-gray-900">{d.symbol}</div>
                  <div className="text-xs text-gray-500">{d.strategy}</div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-semibold text-gray-900">
                    ${Number(d.size_usd || 0).toFixed(2)}
                  </div>
                  <div className="text-xs text-gray-500">
                    {t('Оценка', 'Score')}: {Number(d.score || 0).toFixed(3)}
                  </div>
                </div>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <Metric label="KELLY" value={Number(d.kelly_fraction || 0).toFixed(4)} />
                <Metric label={t('РИСК', 'RISK')} value={`${(Number(d.adaptive_risk || 0) * 100).toFixed(2)}%`} />
              </div>
              <RiskBar value={Number(d.adaptive_risk || 0) * 20} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
