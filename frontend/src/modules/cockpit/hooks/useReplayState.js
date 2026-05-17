/**
 * useReplayState — Replay Pro State Management
 */

import { useEffect, useMemo, useRef, useState, useCallback } from "react";

export function useReplayState(timeline = []) {
  const [mode, setMode] = useState("live");
  const [cursor, setCursor] = useState(Math.max(timeline.length - 1, 0));
  const [speed, setSpeed] = useState(600);
  const [isPlaying, setIsPlaying] = useState(false);
  const timerRef = useRef(null);

  useEffect(() => {
    setCursor(Math.max(timeline.length - 1, 0));
  }, [timeline.length]);

  useEffect(() => {
    if (!isPlaying || mode !== "replay" || timeline.length === 0) return;

    timerRef.current = setInterval(() => {
      setCursor((prev) => {
        if (prev >= timeline.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, speed);

    return () => clearInterval(timerRef.current);
  }, [isPlaying, mode, speed, timeline.length]);

  const activeSnapshot = useMemo(() => {
    if (!timeline.length) return null;
    return timeline[Math.min(cursor, timeline.length - 1)];
  }, [timeline, cursor]);

  const jumpToTimestamp = useCallback((timestamp) => {
    const idx = timeline.findIndex((x) => x.timestamp === timestamp);
    if (idx !== -1) {
      setMode("replay");
      setCursor(idx);
      setIsPlaying(false);
    }
  }, [timeline]);

  const jumpToStart = useCallback(() => {
    setMode("replay");
    setCursor(0);
    setIsPlaying(false);
  }, []);

  const jumpToEnd = useCallback(() => {
    setCursor(timeline.length - 1);
    setIsPlaying(false);
  }, [timeline.length]);

  const togglePlay = useCallback(() => {
    if (cursor >= timeline.length - 1) {
      setCursor(0);
    }
    setIsPlaying((v) => !v);
  }, [cursor, timeline.length]);

  const goLive = useCallback(() => {
    setMode("live");
    setCursor(timeline.length - 1);
    setIsPlaying(false);
  }, [timeline.length]);

  return {
    mode, setMode, cursor, setCursor, speed, setSpeed,
    isPlaying, setIsPlaying, activeSnapshot,
    jumpToTimestamp, jumpToStart, jumpToEnd, togglePlay, goLive,
  };
}

export default useReplayState;
