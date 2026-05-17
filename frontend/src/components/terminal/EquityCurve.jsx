import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function EquityCurve({ lang = 'ru' }) {
  const [data, setData] = useState([]);

  const t = (ru, en) => (lang === 'ru' ? ru : en);

  const load = async () => {
    try {
      const res = await fetch(`${API_URL}/api/trading/portfolio/equity-curve`);
      const json = await res.json();
      setData(json.points || []);
    } catch (e) {
      console.error("EquityCurve load error", e);
    }
  };

  useEffect(() => {
    load();
    const i = setInterval(load, 5000);
    return () => clearInterval(i);
  }, []);

  return (
    <div className="bg-white rounded-xl p-4" data-testid="equity-curve-chart">
      <div className="mb-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-[hsl(var(--fg))]">{t('КРИВАЯ КАПИТАЛА', 'EQUITY CURVE')}</div>
        <div className="text-xs text-[hsl(var(--fg-3))]">{t('Динамика капитала', 'Capital dynamics')}</div>
      </div>

      <div className="h-60">
        {data.length === 0 ? (
          <div className="flex items-center justify-center h-full text-sm text-[hsl(var(--fg-3))]">
            {t('Нет данных', 'No data')}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
              <XAxis dataKey="time" tick={{ fontSize: 11, fill: 'hsl(var(--fg-3))' }} stroke="rgba(0,0,0,0.06)" />
              <YAxis tick={{ fontSize: 11, fill: 'hsl(var(--fg-3))' }} stroke="rgba(0,0,0,0.06)" />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '12px',
                  padding: '8px 12px'
                }}
              />
              <Line type="monotone" dataKey="equity" stroke="hsl(var(--accent))" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
