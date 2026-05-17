import { useEffect, useState } from "react";

const API = process.env.REACT_APP_BACKEND_URL || "";

export function usePositions() {
  const [positions, setPositions] = useState([]);
  const [isConnected, setIsConnected] = useState(false);

  const fetchPositions = async () => {
    try {
      // Use absolute URL + correct endpoint from MMAAARRRGGEE backend
      const res = await fetch(API + "/api/trading/paper/positions", {
        credentials: "include",
      });
      if (!res.ok) {
        // 401/403/404 — treat as no data, not crash
        setPositions([]);
        setIsConnected(false);
        return;
      }
      const data = await res.json();
      // Backend may return: array OR {ok,items} OR {positions} OR {data:{items}}
      let list = [];
      if (Array.isArray(data)) {
        list = data;
      } else if (Array.isArray(data?.items)) {
        list = data.items;
      } else if (Array.isArray(data?.positions)) {
        list = data.positions;
      } else if (Array.isArray(data?.data?.items)) {
        list = data.data.items;
      } else if (Array.isArray(data?.data)) {
        list = data.data;
      }
      setPositions(list);
      setIsConnected(true);
    } catch (err) {
      // Silent — workspace will render "No open positions" gracefully
      setPositions([]);
      setIsConnected(false);
    }
  };

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 5000);
    return () => clearInterval(interval);
  }, []);

  return { positions, refresh: fetchPositions, isConnected };
}
