import { useEffect, useState } from "react";

export function useStrategySummary() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;

    const fetchData = async () => {
      try {
        const res = await fetch("/api/strategy/summary");
        if (!res.ok) throw new Error(`strategy/summary failed: ${res.status}`);
        const json = await res.json();
        if (alive) {
          setData(json);
          setError(null);
        }
      } catch (e) {
        if (alive) setError(e.message);
      }
    };

    fetchData();
    const id = setInterval(fetchData, 5000);

    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return { data, error };
}
