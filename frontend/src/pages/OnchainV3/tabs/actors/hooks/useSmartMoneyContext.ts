import { useState, useCallback, useEffect, useMemo } from 'react';
import type {
  WindowKey, RadarSortKey, FeedFilter, ConvictionTier,
  ActorsResponse, RadarEvent, BrainSignal, PatternEvent,
  MapData, NarrativeData, SmartActor, AlphaSignal, Playbook, ActorItem,
} from '../types/smartMoney';
import { sortItems, deriveCapitalFlows, generateInsight, computeSmartMoneyIndex } from '../helpers';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

export function useSmartMoneyContext(chainId: number) {
  const [timeWindow, setTimeWindow] = useState<WindowKey>('24h');
  const [accData, setAccData] = useState<ActorsResponse | null>(null);
  const [distData, setDistData] = useState<ActorsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [sortBy, setSortBy] = useState<'flow' | 'volume' | 'trades'>('flow');

  const [radarData, setRadarData] = useState<RadarEvent[]>([]);
  const [radarSort, setRadarSort] = useState<RadarSortKey>('confidence');
  const [brainData, setBrainData] = useState<BrainSignal[]>([]);
  const [brainLoading, setBrainLoading] = useState(false);
  const [patternsData, setPatternsData] = useState<PatternEvent[]>([]);
  const [patternsLoading, setPatternsLoading] = useState(false);
  const [radarLoading, setRadarLoading] = useState(false);
  const [mapData, setMapData] = useState<MapData | null>(null);
  const [mapLoading, setMapLoading] = useState(false);
  const [narrativeData, setNarrativeData] = useState<NarrativeData | null>(null);
  const [narrativeLoading, setNarrativeLoading] = useState(false);
  const [actorsData, setActorsData] = useState<SmartActor[]>([]);
  const [allSignals, setAllSignals] = useState<AlphaSignal[]>([]);
  const [feedData, setFeedData] = useState<AlphaSignal[]>([]);
  const [feedFilter, setFeedFilter] = useState<FeedFilter>('all');
  const [convictionTier, setConvictionTier] = useState<ConvictionTier>('high');
  const [playbooksData, setPlaybooksData] = useState<Playbook[]>([]);
  const [contextLoading, setContextLoading] = useState(false);

  const loadBuySell = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [accRes, distRes] = await Promise.all([
        fetch(`${API_BASE}/api/v10/onchain-v2/market/actors/list?chainId=${chainId}&window=${timeWindow}&direction=accumulation&limit=20`),
        fetch(`${API_BASE}/api/v10/onchain-v2/market/actors/list?chainId=${chainId}&window=${timeWindow}&direction=distribution&limit=20`),
      ]);
      const accJson = await accRes.json();
      const distJson = await distRes.json();
      setAccData(accJson);
      setDistData(distJson);
      setLastUpdate(new Date());
    } catch (e: any) {
      console.warn('[SmartMoney] load error:', e.message);
    } finally {
      setLoading(false);
    }
  }, [chainId, timeWindow]);

  const loadContext = useCallback(async () => {
    setContextLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/onchain/smart-money/context?chainId=${chainId}&window=${timeWindow}`);
      const json = await res.json();
      if (json.ok) {
        setNarrativeData(json.narrative || null);
        setBrainData(json.brain || []);
        setPatternsData(json.patterns || []);
        setRadarData(json.events || []);
        setMapData({
          routes: json.routes?.routes || [],
          destination_heat: json.routes?.destination_heat || [],
          source_heat: json.routes?.source_heat || [],
          flow_summary: json.routes?.flow_summary || {},
        });
        setActorsData(json.actors || []);
        setAllSignals(json.signals || []);
        setPlaybooksData(json.playbooks || []);
        setLastUpdate(new Date());
      }
    } catch (e: any) {
      console.warn('[SmartMoney] context error:', e.message);
    } finally {
      setContextLoading(false);
      setNarrativeLoading(false);
      setBrainLoading(false);
      setPatternsLoading(false);
      setRadarLoading(false);
      setMapLoading(false);
    }
  }, [chainId, timeWindow]);

  // Client-side feed filtering
  useEffect(() => {
    let filtered = [...allSignals];
    if (convictionTier === 'high') filtered = filtered.filter(s => s.conviction >= 60);
    else if (convictionTier === 'medium') filtered = filtered.filter(s => s.conviction >= 50 && s.conviction < 60);
    else if (convictionTier === 'low') filtered = filtered.filter(s => s.conviction >= 40 && s.conviction < 50);
    if (feedFilter !== 'all') filtered = filtered.filter(s => s.signal_type === feedFilter);
    setFeedData(filtered);
  }, [allSignals, feedFilter, convictionTier]);

  useEffect(() => { loadBuySell(); loadContext(); }, [timeWindow, chainId]);

  // Client-side radar sort
  const sortedRadarData = useMemo(() => {
    const data = [...radarData];
    if (radarSort === 'confidence') data.sort((a: any, b: any) => (b.confidence || 0) - (a.confidence || 0));
    else if (radarSort === 'net_flow') data.sort((a: any, b: any) => Math.abs(b.net_flow_usd || 0) - Math.abs(a.net_flow_usd || 0));
    else if (radarSort === 'impact') data.sort((a: any, b: any) => (b.impact_score || 0) - (a.impact_score || 0));
    else if (radarSort === 'recency') {
      const rk = (e: any) => { const la = e.last_activity || ''; if (la.includes('s ago')) return 0; if (la.includes('m ago')) return 1; if (la.includes('h ago')) return 2; return 3; };
      data.sort((a: any, b: any) => rk(a) - rk(b));
    }
    return data;
  }, [radarData, radarSort]);

  // Derived data
  const buyers = useMemo(() => {
    const items = (accData?.items || []).filter((i: ActorItem) => i.netUsd > 0);
    return sortItems(items, sortBy);
  }, [accData, sortBy]);
  const sellers = useMemo(() => {
    const items = (distData?.items || []).filter((i: ActorItem) => i.netUsd < 0);
    return sortItems(items, sortBy);
  }, [distData, sortBy]);
  const totalBuy = useMemo(() => buyers.reduce((s: number, i: ActorItem) => s + i.netUsd, 0), [buyers]);
  const totalSell = useMemo(() => sellers.reduce((s: number, i: ActorItem) => s + i.netUsd, 0), [sellers]);
  const netFlow = totalBuy + totalSell;
  const isBullish = netFlow > 0;
  const capitalFlows = useMemo(() => {
    // Build wallet lookup from context data
    const lookup: Record<string, string[]> = {};
    for (const actor of actorsData) {
      if (actor.wallet && actor.wallet_addresses?.length) {
        lookup[actor.wallet] = actor.wallet_addresses;
        if (actor.name) lookup[actor.name] = actor.wallet_addresses;
      }
    }
    return deriveCapitalFlows(buyers, sellers, lookup);
  }, [buyers, sellers, actorsData]);
  const insight = useMemo(() => generateInsight(totalBuy, totalSell, buyers, sellers), [totalBuy, totalSell, buyers, sellers]);
  const smi = useMemo(() => computeSmartMoneyIndex(totalBuy, totalSell), [totalBuy, totalSell]);

  return {
    // State
    timeWindow, setTimeWindow,
    loading, error, contextLoading, lastUpdate,
    sortBy, setSortBy,
    radarSort, setRadarSort,
    feedFilter, setFeedFilter,
    convictionTier, setConvictionTier,
    // Data
    narrativeData, narrativeLoading,
    brainData, brainLoading,
    patternsData, patternsLoading,
    sortedRadarData, radarLoading,
    mapData, mapLoading,
    actorsData,
    allSignals, feedData,
    playbooksData,
    buyers, sellers,
    totalBuy, totalSell, netFlow, isBullish,
    capitalFlows, insight, smi,
    accData,
    // Actions
    loadBuySell, loadContext,
    refresh: () => { loadBuySell(); loadContext(); },
  };
}
