import { useState, useCallback } from 'react';

export function useCexFlow(filteredGraphEdges, nodeDataMap) {
  const [cexRoutes, setCexRoutes] = useState([]);
  const [isCexFlowMode, setIsCexFlowMode] = useState(false);
  const [lockedCexData, setLockedCexData] = useState(null);
  const [cexUnlockTrigger, setCexUnlockTrigger] = useState(0);
  const [expandedCluster, setExpandedCluster] = useState(null);
  const [copiedAddr, setCopiedAddr] = useState(null);
  const [hideWeakLinks, setHideWeakLinks] = useState(false);
  const [isPathsCollapsed, setIsPathsCollapsed] = useState(false);

  const handleCloseCluster = useCallback(() => {
    setExpandedCluster(null);
    setHideWeakLinks(false);
  }, []);

  const handleCopyAddr = useCallback((addr) => {
    navigator.clipboard.writeText(addr);
    setCopiedAddr(addr);
    setTimeout(() => setCopiedAddr(null), 2000);
  }, []);

  const handleCexRouteUnlock = useCallback(() => {
    setLockedCexData(null);
    setExpandedCluster(null);
    setCexUnlockTrigger(v => v + 1);
  }, []);

  const handleCexRouteLock = useCallback((lockedRouteIndices) => {
    if (!lockedRouteIndices) { setLockedCexData(null); return; }
    const routes = cexRoutes.filter((_, idx) => lockedRouteIndices.has(idx));
    const allSegKeys = new Set();
    const entrySegKeys = new Set();
    const exitSegKeys = new Set();
    const nodeIds = new Set();
    for (const route of routes) {
      const path = route.path || [];
      path.forEach(id => nodeIds.add(id));
      for (let i = 0; i < path.length - 1; i++) {
        allSegKeys.add([path[i], path[i + 1]].sort().join('|'));
      }
      if (path.length >= 2) {
        entrySegKeys.add([path[0], path[1]].sort().join('|'));
        exitSegKeys.add([path[path.length - 2], path[path.length - 1]].sort().join('|'));
      }
    }
    const edgeStats = new Map();
    let txCount = 0;
    for (const edge of (filteredGraphEdges || [])) {
      const s = edge.source || '';
      const t = edge.target || '';
      const ek = [s, t].sort().join('|');
      if (!allSegKeys.has(ek)) continue;
      if (!edgeStats.has(ek)) edgeStats.set(ek, { volume: 0, txCount: 0, edgeCount: 0 });
      const st = edgeStats.get(ek);
      st.edgeCount++;
      const amt = edge.amountUsd || edge.volumeUsd || edge.volume_usd || 0;
      st.volume += amt;
      st.txCount += edge.txCount || edge.tx_count || 1;
      txCount += edge.txCount || edge.tx_count || 1;
    }
    let inflow = 0, outflow = 0, totalVolume = 0;
    for (const [segKey, st] of edgeStats) {
      totalVolume += st.volume;
      if (entrySegKeys.has(segKey)) inflow += st.volume;
      if (exitSegKeys.has(segKey)) outflow += st.volume;
    }
    const resolvedRoutes = routes.map(route => {
      const path = route.path || [];
      const resolvedPath = path.map(id => {
        const n = nodeDataMap.get(id);
        return { id, label: n?.label || n?.fullName || id.split(':').pop() || id, type: (n?.type || '').toLowerCase() };
      });
      const segments = [];
      for (let i = 0; i < path.length - 1; i++) {
        const ek = [path[i], path[i + 1]].sort().join('|');
        const st = edgeStats.get(ek) || { volume: 0, txCount: 0, edgeCount: 0 };
        segments.push({ source: resolvedPath[i], target: resolvedPath[i + 1], ...st });
      }
      const maxVol = Math.max(...segments.map(s => s.volume), 1);
      const maxTx = Math.max(...segments.map(s => s.txCount), 1);
      const maxEdge = Math.max(...segments.map(s => s.edgeCount), 1);
      for (const seg of segments) {
        seg.confidence = Math.round(
          ((seg.edgeCount / maxEdge) * 0.3 + (seg.volume / maxVol) * 0.4 + (seg.txCount / maxTx) * 0.3) * 100
        ) / 100;
      }
      return { ...route, resolvedPath, segments };
    });
    const allWashFlags = [];
    const seenFlagTypes = new Set();
    let maxWashScore = 0;
    const dbAlerts = [];
    for (const route of resolvedRoutes) {
      maxWashScore = Math.max(maxWashScore, route.wash_score || 0);
      for (const flag of (route.wash_flags || [])) {
        const key = `${flag.type}:${route.from_cex}:${route.to_cex}`;
        if (!seenFlagTypes.has(key)) {
          seenFlagTypes.add(key);
          allWashFlags.push(flag);
        }
      }
      for (const alert of (route.db_wash_alerts || [])) {
        if (!dbAlerts.find(a => a.alert_id === alert.alert_id)) {
          dbAlerts.push(alert);
        }
      }
    }
    setLockedCexData({
      routes: resolvedRoutes, inflow, outflow,
      net: inflow - outflow, total: totalVolume,
      edges: allSegKeys.size, txCount, nodes: nodeIds.size,
      washScore: maxWashScore,
      washFlags: allWashFlags,
      dbWashAlerts: dbAlerts,
    });
  }, [cexRoutes, filteredGraphEdges, nodeDataMap]);

  return {
    cexRoutes, setCexRoutes,
    isCexFlowMode, setIsCexFlowMode,
    lockedCexData,
    cexUnlockTrigger,
    expandedCluster, setExpandedCluster,
    copiedAddr,
    hideWeakLinks, setHideWeakLinks,
    isPathsCollapsed, setIsPathsCollapsed,
    handleCloseCluster, handleCopyAddr, handleCexRouteUnlock, handleCexRouteLock,
  };
}
