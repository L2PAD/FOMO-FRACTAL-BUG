import { useEffect, useState } from "react";

export function useStrategyRecentDecisions() {
  const [data, setData] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;

    const fetchData = async () => {
      try {
        const res = await fetch("/api/strategy/decisions/recent");
        if (!res.ok) throw new Error(`decisions/recent failed: ${res.status}`);
        const json = await res.json();
        if (alive) {
          setData(Array.isArray(json) ? json : []);
          setError(null);
        }
      } catch (e) {
        if (alive) setError(e.message);
      }
    };

    fetchData();
    const id = setInterval(fetchData, 3000);

    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return { data, error };
}
