import { useEffect, useState } from "react";

export function useExecutionFeed() {
  const [events, setEvents] = useState([]);

  const fetchEvents = async () => {
    try {
      const res = await fetch("/api/execution/feed");
      const data = await res.json();
      setEvents(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("[useExecutionFeed] Error:", err);
      setEvents([]);
    }
  };

  useEffect(() => {
    fetchEvents();
    const interval = setInterval(fetchEvents, 2000);
    return () => clearInterval(interval);
  }, []);

  return { events, refresh: fetchEvents };
}
