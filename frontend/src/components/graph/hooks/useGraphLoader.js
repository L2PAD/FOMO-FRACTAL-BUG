import { useCallback } from 'react';
import { loadGraph } from '../../../graph/services/graphDataService';

export function useGraphLoader(activeChains) {
  const fetchEntityGraph = useCallback(async (entityId, graphMode, graphLevel) => {
    const isAddress = entityId.startsWith('0x') || entityId.includes(':0x');
    const dataMode = isAddress ? 'address' : 'actor';
    const data = await loadGraph({ mode: dataMode, identifier: entityId, graphMode, graphLevel, chains: activeChains });
    return { data, dataMode };
  }, [activeChains]);

  const fetchDiscoveryGraph = useCallback(async (graphMode) => {
    return await loadGraph({ mode: 'discovery', identifier: null, graphMode, chains: activeChains });
  }, [activeChains]);

  return { fetchEntityGraph, fetchDiscoveryGraph };
}
