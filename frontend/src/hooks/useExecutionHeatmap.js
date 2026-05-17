import { useEffect, useState } from "react";

export default function useExecutionHeatmap(symbol) {
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!symbol) return;

    let active = true;

    async function load() {
      try {
        const res = await fetch(`/api/trading/execution/heatmap?symbol=${symbol}`);
        const json = await res.json();
        if (active) setData(json.ok ? json : null);
      } catch {
        if (active) setData(null);
      }
    }

    load();
    const i = setInterval(load, 3000);

    return () => {
      active = false;
      clearInterval(i);
    };
  }, [symbol]);

  return data;
}
