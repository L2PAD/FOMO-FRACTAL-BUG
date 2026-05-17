import React, { useState, useEffect } from 'react';
import { getOnchainChart, OnchainChartResponse } from './onchainApi';
import { OnchainContextCard } from './OnchainContextCard';
import { OnchainContextChart } from './OnchainContextChart';

interface OnchainContextSectionProps {
  symbol: string;
}

export function OnchainContextSection({ symbol }: OnchainContextSectionProps) {
  const [data, setData] = useState<OnchainChartResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function fetchData() {
      try {
        setLoading(true);
        const cleanSymbol = symbol.replace('USDT', '').replace('USD', '');
        const result = await getOnchainChart(cleanSymbol, '30d');
        
        if (mounted) {
          setData(result);
          setError(null);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Failed to load');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    fetchData();

    // Refresh every 60 seconds
    const interval = setInterval(fetchData, 60000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [symbol]);

  if (error) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="text-sm text-red-600">Failed to load On-Chain data: {error}</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <OnchainContextCard
        latest={data?.latest || null}
        policyVersion={data?.policy?.version || null}
        provider={data?.provider || 'unknown'}
        loading={loading}
      />
      <OnchainContextChart
        series={data?.series || []}
        loading={loading}
      />
    </div>
  );
}
