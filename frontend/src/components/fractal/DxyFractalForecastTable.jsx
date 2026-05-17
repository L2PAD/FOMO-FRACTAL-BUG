/**
 * DXY Fractal Forecast Table — Container
 * Fetches from /api/fractal/dxy/forecasts, renders BaseForecastTable
 */
import React, { useState, useEffect, useCallback } from 'react';
import BaseForecastTable from './BaseForecastTable';

const API = process.env.REACT_APP_BACKEND_URL;

export default function DxyFractalForecastTable({ horizon: initialHorizon = '7D', limit = 40 }) {
  const [activeHorizon, setActiveHorizon] = useState(initialHorizon);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/fractal/dxy/forecasts?horizon=${activeHorizon}&limit=${limit}`);
      if (!res.ok) throw new Error(`${res.status}`);
      const json = await res.json();
      if (json.ok) setData(json);
    } catch {}
    setLoading(false);
  }, [activeHorizon, limit]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { setActiveHorizon(initialHorizon); }, [initialHorizon]);

  return (
    <BaseForecastTable
      data={data}
      loading={loading}
      activeHorizon={activeHorizon}
      onHorizonChange={setActiveHorizon}
      testIdPrefix="dxy-forecast"
    />
  );
}
