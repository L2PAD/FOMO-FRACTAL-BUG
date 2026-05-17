import { useEffect, useState } from "react";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function useMarketCandles(symbol, timeframe = "4h") {
  const [candles, setCandles] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        
        // Map timeframe to Coinbase API format
        const tfMap = {
          "1h": "1h",
          "4h": "6h",
          "1d": "1d"
        };
        const coinbaseTf = tfMap[timeframe] || "6h";
        
        const res = await fetch(
          `${API_URL}/api/provider/coinbase/candles/${symbol.replace('USDT', '')}?timeframe=${coinbaseTf}&limit=200`
        );
        const data = await res.json();

        if (!cancelled && data.ok) {
          setCandles(data.candles || []);
        }
      } catch (e) {
        if (!cancelled) {
          console.error('Candles fetch error:', e);
          setCandles([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    if (symbol) load();

    return () => {
      cancelled = true;
    };
  }, [symbol, timeframe]);

  return { candles, loading };
}
