import { useState, useCallback, useEffect } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * useGraphSearch — search state + orchestration.
 * Does NOT know about graph, intelligence, or relations.
 * Communicates entity selection via onSelectEntity callback.
 *
 * Contract:
 *   readonly: query, suggestions, isSearching, isResolving, showSuggestions
 *   actions:  setQuery, executeSearch, handleKeyDown, acceptSuggestion, clearSearch
 */
export function useGraphSearch({ onSelectEntity }) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [topSuggestion, setTopSuggestion] = useState(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isResolving, setIsResolving] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);

  // ── Suggest (debounced by effect below) ──
  const fetchSuggestions = useCallback(async (q) => {
    if (!q || q.length < 2) { setSuggestions([]); setTopSuggestion(null); setShowSuggestions(false); return; }
    setIsSearching(true);
    try {
      const res = await fetch(`${API_URL}/api/graph-core/search/suggest?q=${encodeURIComponent(q)}&limit=8`);
      if (res.ok) {
        const data = await res.json();
        const results = data.results || [];
        setSuggestions(results);
        setTopSuggestion(results[0] || null);
        setShowSuggestions(results.length > 0);
      }
    } catch { setSuggestions([]); setTopSuggestion(null); setShowSuggestions(false); }
    finally { setIsSearching(false); }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => fetchSuggestions(query), 200);
    return () => clearTimeout(timer);
  }, [query, fetchSuggestions]);

  // ── Resolve + Select ──
  const selectEntity = useCallback((entity) => {
    onSelectEntity(entity);
    setTopSuggestion(null);
    setSuggestions([]);
    setShowSuggestions(false);
  }, [onSelectEntity]);

  const executeSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) return;
    setIsResolving(true);
    try {
      if (q.startsWith('0x') && q.length >= 10) {
        selectEntity({ id: `wallet:${q.toLowerCase()}:ethereum`, label: q, type: 'wallet' });
        return;
      }
      const resolveRes = await fetch(`${API_URL}/api/graph-core/resolve?q=${encodeURIComponent(q)}`);
      if (resolveRes.ok) {
        const data = await resolveRes.json();
        if (data.found && data.node_id) {
          selectEntity({ id: data.node_id, label: data.label || q, type: data.type || 'wallet' });
          return;
        }
      }
      const advRes = await fetch(`${API_URL}/api/graph/search/advanced?q=${encodeURIComponent(q)}&auto_create=true`);
      if (advRes.ok) {
        const data = await advRes.json();
        if (data.found && data.entity) {
          const e = data.entity;
          selectEntity({ id: e.id || `${e.entity_type}:${e.entity_id}`, label: e.label || q, type: e.entity_type || e.type });
          return;
        }
      }
      const basicRes = await fetch(`${API_URL}/api/graph/search?q=${encodeURIComponent(q)}`);
      if (basicRes.ok) {
        const data = await basicRes.json();
        if (data.results?.length > 0) {
          const e = data.results[0];
          selectEntity({ id: e.id, label: e.label || q, type: e.type });
          return;
        }
      }
      selectEntity({ id: `wallet:${q.toLowerCase()}:ethereum`, label: q, type: 'wallet' });
    } catch {
      if (topSuggestion) {
        selectEntity({ id: topSuggestion.id, label: (topSuggestion.label || '').replace(/_/g, ' '), type: topSuggestion.type });
      }
    } finally { setIsResolving(false); }
  }, [query, topSuggestion, selectEntity]);

  const acceptSuggestion = useCallback((item) => {
    const s = item || topSuggestion;
    if (s) {
      const cleanLabel = (s.label || '').replace(/_/g, ' ');
      setQuery(cleanLabel);
      selectEntity({ id: s.node_id || s.id, label: cleanLabel, type: s.type });
    }
  }, [topSuggestion, selectEntity]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      setShowSuggestions(false);
      if (topSuggestion?.label?.toLowerCase().startsWith(query.toLowerCase())) {
        const cleanLabel = (topSuggestion.label || '').replace(/_/g, ' ');
        setQuery(cleanLabel);
        selectEntity({ id: topSuggestion.node_id || topSuggestion.id, label: cleanLabel, type: topSuggestion.type });
      } else { executeSearch(); }
    }
    if (e.key === 'Escape') { setShowSuggestions(false); }
  }, [topSuggestion, query, selectEntity, executeSearch]);

  const clearSearch = useCallback(() => {
    setQuery('');
    setSuggestions([]);
    setTopSuggestion(null);
    setShowSuggestions(false);
  }, []);

  const openSuggestions = useCallback(() => {
    if (suggestions.length > 0) setShowSuggestions(true);
  }, [suggestions]);

  const closeSuggestionsDelayed = useCallback(() => {
    setTimeout(() => setShowSuggestions(false), 200);
  }, []);

  return {
    // readonly
    query, suggestions, isSearching, isResolving, showSuggestions, topSuggestion,
    // actions
    setQuery, executeSearch, handleKeyDown, acceptSuggestion, clearSearch,
    openSuggestions, closeSuggestionsDelayed,
  };
}
