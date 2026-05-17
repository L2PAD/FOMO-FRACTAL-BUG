import { useState, useEffect } from 'react';

export const usePortfolioTimelineEvents = (interval = 3000) => {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/portfolio/timeline-events`);
        if (!response.ok) throw new Error(`Failed to fetch events: ${response.status}`);
        const result = await response.json();
        setEvents(result || []);
        setLoading(false);
      } catch (err) {
        console.error('[usePortfolioTimelineEvents] Error:', err);
        setLoading(false);
      }
    };

    fetchEvents();
    const intervalId = setInterval(fetchEvents, interval);
    return () => clearInterval(intervalId);
  }, [interval]);

  return { events, loading };
};
