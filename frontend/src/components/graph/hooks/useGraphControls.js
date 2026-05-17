import { useState, useCallback, useEffect, useRef } from 'react';
import { EDGE_TYPES } from '../../../graph/constants/edgeTypes';

export function useGraphControls() {
  const [showFilters, setShowFilters] = useState(false);
  const [showLeaderboard, setShowLeaderboard] = useState(false);
  const [showPlayback, setShowPlayback] = useState(false);
  const [playbackActive, setPlaybackActive] = useState(false);
  const [playbackHighlights, setPlaybackHighlights] = useState(null);
  const [isGraphFullscreen, setIsGraphFullscreen] = useState(false);
  const graphContainerRef = useRef(null);
  const [activeToolPanel, setActiveToolPanel] = useState(null);
  const [edgeTypeFilters, setEdgeTypeFilters] = useState(
    Object.fromEntries(Object.keys(EDGE_TYPES).map(k => [k, true]))
  );

  const handlePlaybackActive = useCallback((active) => {
    setPlaybackActive(active);
    if (!active) setPlaybackHighlights(null);
  }, []);

  const resetFilters = useCallback(() => {
    setEdgeTypeFilters(Object.fromEntries(Object.keys(EDGE_TYPES).map(k => [k, true])));
  }, []);

  const toggleGraphFullscreen = useCallback(async () => {
    const el = graphContainerRef.current;
    if (!el) return;
    try {
      if (!document.fullscreenElement) await el.requestFullscreen();
      else await document.exitFullscreen();
    } catch (e) { console.error('Fullscreen error:', e); }
  }, []);

  useEffect(() => {
    const onFsChange = () => setIsGraphFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onFsChange);
    return () => document.removeEventListener('fullscreenchange', onFsChange);
  }, []);

  return {
    showFilters, setShowFilters,
    showLeaderboard, setShowLeaderboard,
    showPlayback, setShowPlayback,
    playbackActive, playbackHighlights, setPlaybackHighlights,
    isGraphFullscreen, graphContainerRef,
    activeToolPanel, setActiveToolPanel,
    edgeTypeFilters, setEdgeTypeFilters,
    handlePlaybackActive, resetFilters, toggleGraphFullscreen,
  };
}
