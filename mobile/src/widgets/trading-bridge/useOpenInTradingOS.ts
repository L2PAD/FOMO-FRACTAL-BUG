/**
 * useOpenInTradingOS — atomic intelligence → trading handoff.
 *
 * One call:
 *   1. preserves the asset context (universal asset state)
 *   2. switches mode to TRADING
 *   3. lands the user on the requested Trading OS tab (default: EXECUTION)
 *
 * Used by the bridge components inside Feed / Edge / Signals / IntelHome.
 */
import { useCallback } from 'react';
import { useAppMode, TradingTab } from '../../stores/app-mode.store';
import { useAssetStore } from '../../stores/asset.store';

export function useOpenInTradingOS() {
  const switchToTrading = useAppMode((s) => s.switchToTrading);
  const setTradingTab = useAppMode((s) => s.setTradingTab);
  const setAsset = useAssetStore((s) => s.setCurrentAsset);

  return useCallback(
    (asset?: string | null, tab: TradingTab = 'EXECUTION') => {
      if (asset && typeof asset === 'string') setAsset(asset.replace('USDT', '').toUpperCase());
      switchToTrading();
      setTradingTab(tab);
    },
    [switchToTrading, setTradingTab, setAsset],
  );
}
