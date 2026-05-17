import { useEffect, useState } from "react";

export function useFills() {
  const [fills, setFills] = useState([]);

  const fetchFills = async () => {
    try {
      const res = await fetch("/api/exchange/fills");
      const data = await res.json();
      setFills(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("[useFills] Error:", err);
      setFills([]);
    }
  };

  useEffect(() => {
    fetchFills();
    const interval = setInterval(fetchFills, 3000);
    return () => clearInterval(interval);
  }, []);

  return { fills, refresh: fetchFills };
}
