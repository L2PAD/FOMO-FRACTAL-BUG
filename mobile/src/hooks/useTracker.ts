/**
 * useTracker — Automatic Behavior Tracking Hook
 *
 * Tracks: screen views, time on screen, asset views, taps
 * Sends events to /api/mobile/behavior/track
 *
 * Usage:
 *   useTracker('HOME', { symbol: 'BTC' });
 */

import { useEffect, useRef } from 'react';
import { mobileApi } from '../services/api/mobile-api';

export function useTracker(
  screenName: string,
  data?: Record<string, any>,
  options?: { trackTime?: boolean }
) {
  const startTime = useRef(Date.now());
  const tracked = useRef(false);

  useEffect(() => {
    if (tracked.current) return;
    tracked.current = true;
    startTime.current = Date.now();

    // Track screen view
    mobileApi.trackEvent('VIEW_SCREEN', {
      screen: screenName,
      ...data,
    }).catch(() => {});

    // Track asset view if symbol present
    if (data?.symbol) {
      mobileApi.trackEvent('VIEW_ASSET', {
        symbol: data.symbol,
        screen: screenName,
      }).catch(() => {});
    }

    return () => {
      // Track time on screen when leaving
      if (options?.trackTime !== false) {
        const seconds = Math.round((Date.now() - startTime.current) / 1000);
        if (seconds >= 3) { // Only track if stayed > 3s
          mobileApi.trackEvent('TIME_ON_SCREEN', {
            screen: screenName,
            seconds,
            symbol: data?.symbol,
          }).catch(() => {});
        }
      }
    };
  }, [screenName]);
}

/**
 * Track a specific user action (tap, click, etc.)
 */
export function trackAction(action: string, data?: Record<string, any>) {
  mobileApi.trackEvent(action, data).catch(() => {});
}
