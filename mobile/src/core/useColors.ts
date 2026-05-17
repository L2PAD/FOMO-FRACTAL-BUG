import { useMemo } from 'react';
import { usePreferencesStore } from '../stores/preferences.store';
import { getTheme, AppThemeColors } from './themes';

/**
 * Shared hook: returns current theme colors based on user preference.
 * Use this in every screen/component that needs dynamic theme support.
 */
export function useColors(): AppThemeColors {
  const resolved = usePreferencesStore((s) => s.resolvedTheme);
  return useMemo(() => getTheme(resolved).colors, [resolved]);
}
