import { useState, useEffect, useMemo, useCallback } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const ITEMS_PER_PAGE = 10;

/**
 * useGraphRelations — loads relations for a given entityId.
 * Does NOT own selectedEntity. Receives entityId as parameter.
 * Does NOT trigger graph reload or touch other domains.
 *
 * Contract:
 *   readonly: relations, loading, page, totalPages, paginatedRelations
 *   actions:  setPage, navigateToEntity (via callback)
 */
export function useGraphRelations({ entityId, fallbackEdges, onNavigateToEntity }) {
  const [relations, setRelations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);

  useEffect(() => {
    if (!entityId) { setRelations([]); return; }
    const load = async () => {
      setLoading(true);
      try {
        const coreRes = await fetch(`${API_URL}/api/graph-core/edges/${encodeURIComponent(entityId)}?limit=100`);
        const coreData = coreRes.ok ? await coreRes.json() : { edges: [] };
        let edges = coreData.edges || [];
        if (edges.length === 0) {
          const [type, ...rest] = entityId.split(':');
          const id = rest.join(':');
          if (type && id) {
            const legacyRes = await fetch(`${API_URL}/api/graph/edges/${type}/${id}?limit=100`);
            const legacyData = legacyRes.ok ? await legacyRes.json() : { edges: [] };
            edges = legacyData.edges || [];
          }
        }
        if (edges.length === 0 && fallbackEdges?.length > 0) {
          edges = fallbackEdges
            .filter(e => {
              const src = typeof e.source === 'object' ? e.source.id : e.source;
              const tgt = typeof e.target === 'object' ? e.target.id : e.target;
              return src === entityId || tgt === entityId;
            })
            .map(e => {
              const src = typeof e.source === 'object' ? e.source.id : e.source;
              const tgt = typeof e.target === 'object' ? e.target.id : e.target;
              return { id: e.id, source: src, target: tgt, source_label: '', target_label: '', relation: e.type || 'transfer', type: e.type || 'transfer' };
            });
        }
        const seenKeys = new Set();
        setRelations(edges.map(edge => {
          const isOut = edge.source === entityId;
          const target = isOut ? edge.target : edge.source;
          const label = isOut ? edge.target_label : edge.source_label;
          return {
            id: edge.id, type: target.split(':')[0],
            entity: label || target.split(':')[1] || target,
            entityId: target,
            relation: (edge.relation || edge.type || 'transfer').replace(/_/g, ' '),
            direction: isOut ? 'out' : 'in',
            _key: `${target}:${edge.relation || edge.type}`,
          };
        }).filter(rel => { if (seenKeys.has(rel._key)) return false; seenKeys.add(rel._key); return true; }));
      } catch { setRelations([]); }
      finally { setLoading(false); }
    };
    load();
    setPage(1);
  }, [entityId, fallbackEdges]);

  const totalPages = useMemo(() => Math.ceil(relations.length / ITEMS_PER_PAGE), [relations.length]);
  const paginatedRelations = useMemo(() => relations.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE), [relations, page]);

  const navigateToEntity = useCallback((rel) => {
    onNavigateToEntity({ id: rel.entityId, label: rel.entity, type: rel.type });
  }, [onNavigateToEntity]);

  return {
    // readonly
    relations, loading, page, totalPages, paginatedRelations,
    // actions
    setPage, navigateToEntity,
  };
}
