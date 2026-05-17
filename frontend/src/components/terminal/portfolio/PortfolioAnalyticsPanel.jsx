import { useEffect, useState } from "react";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function PortfolioAnalyticsPanel() {
  const [data, setData] = useState([]);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_URL}/api/trading/portfolio/equity-curve`);
        const json = await res.json();
        setData(json.points || []);
      } catch (e) {
        console.error('Equity curve fetch error:', e);
      }
    }

    load();
    const i = setInterval(load, 10000);
    return () => clearInterval(i);
  }, []);

  return (
    <div className="border border-neutral-200 rounded-lg p-4 h-[220px]">
      <div className="text-sm font-semibold mb-2 text-neutral-900">
        Equity Curve
      </div>

      <div className="text-xs text-neutral-400">
        Points: {data.length}
      </div>

      {/* Chart placeholder - can add Recharts later */}
      <div className="mt-4 h-32 bg-neutral-50 rounded flex items-center justify-center text-xs text-neutral-400">
        Chart Integration - Coming Soon
      </div>
    </div>
  );
}
