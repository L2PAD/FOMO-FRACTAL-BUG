import { create } from 'zustand';
import { Appearance } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

const PREFS_KEY = 'fomo_prefs';

export type ThemeMode = 'dark' | 'light' | 'system';
export type AppLanguage = 'en' | 'ru' | 'uk';
export type StartScreen = 'HOME' | 'FEED' | 'EDGE';

interface NotifSettings {
  decisionChanges: boolean;
  confidenceShifts: boolean;
  keyEvents: boolean;
  edgeOpportunities: boolean;
  edgeHigh: boolean;
  highImpactFeed: boolean;
  allFeedEvents: boolean;
  billing: boolean;
  systemUpdates: boolean;
  push: boolean;
  email: boolean;
}

const DEFAULT_NOTIF: NotifSettings = {
  decisionChanges: true,
  confidenceShifts: true,
  keyEvents: true,
  edgeOpportunities: false,
  edgeHigh: true,
  highImpactFeed: true,
  allFeedEvents: false,
  billing: true,
  systemUpdates: false,
  push: true,
  email: false,
};

interface PreferencesState {
  themeMode: ThemeMode;
  resolvedTheme: 'dark' | 'light';
  language: AppLanguage;
  startScreen: StartScreen;
  hapticsEnabled: boolean;
  notificationSettings: NotifSettings;
  prefsHydrated: boolean;

  setThemeMode: (mode: ThemeMode) => void;
  setLanguage: (lang: AppLanguage) => void;
  setStartScreen: (screen: StartScreen) => void;
  setHapticsEnabled: (enabled: boolean) => void;
  updateNotificationSetting: (key: string, value: boolean) => void;
  hydrateFromProfile: (prefs: any) => void;
}

function resolveTheme(mode: ThemeMode): 'dark' | 'light' {
  if (mode === 'system') {
    return Appearance.getColorScheme() === 'light' ? 'light' : 'dark';
  }
  return mode;
}

// Persist theme+language to local storage so it survives logout/restart
async function _persistLocal(partial: { themeMode?: ThemeMode; language?: AppLanguage }) {
  try {
    const raw = await AsyncStorage.getItem(PREFS_KEY);
    const current = raw ? JSON.parse(raw) : {};
    await AsyncStorage.setItem(PREFS_KEY, JSON.stringify({ ...current, ...partial }));
  } catch {}
}

// Hydrate from AsyncStorage on app launch (before login)
async function _hydrateFromLocal() {
  try {
    const raw = await AsyncStorage.getItem(PREFS_KEY);
    if (raw) {
      const data = JSON.parse(raw);
      const u: any = {};
      if (data.themeMode && ['dark', 'light'].includes(data.themeMode)) {
        u.themeMode = data.themeMode;
        u.resolvedTheme = resolveTheme(data.themeMode);
      } else if (data.themeMode === 'system') {
        // Migrate from removed 'system' option to 'dark'
        u.themeMode = 'dark';
        u.resolvedTheme = 'dark';
      }
      if (data.language && ['en', 'ru', 'uk'].includes(data.language)) {
        u.language = data.language;
      }
      if (Object.keys(u).length > 0) {
        usePreferencesStore.setState(u);
      }
    }
  } catch {}
  // Mark hydration as complete regardless of result
  usePreferencesStore.setState({ prefsHydrated: true });
}

export const usePreferencesStore = create<PreferencesState>((set, get) => ({
  themeMode: 'dark',
  resolvedTheme: 'dark',
  language: 'en',
  startScreen: 'HOME',
  hapticsEnabled: true,
  notificationSettings: { ...DEFAULT_NOTIF },
  prefsHydrated: false,

  setThemeMode: (mode) => {
    set({ themeMode: mode, resolvedTheme: resolveTheme(mode) });
    _persistLocal({ themeMode: mode });
  },
  setLanguage: (lang) => {
    set({ language: lang });
    _persistLocal({ language: lang });
  },
  setStartScreen: (screen) => set({ startScreen: screen }),
  setHapticsEnabled: (enabled) => set({ hapticsEnabled: enabled }),
  updateNotificationSetting: (key, value) =>
    set((state) => ({
      notificationSettings: { ...state.notificationSettings, [key]: value },
    })),
  hydrateFromProfile: (prefs) => {
    if (!prefs) return;
    const u: Partial<PreferencesState> = {};
    if (prefs.theme && ['dark', 'light', 'system'].includes(prefs.theme)) {
      u.themeMode = prefs.theme as ThemeMode;
      u.resolvedTheme = resolveTheme(prefs.theme as ThemeMode);
      _persistLocal({ themeMode: prefs.theme as ThemeMode });
    }
    if (prefs.language && ['en', 'ru', 'uk'].includes(prefs.language)) {
      u.language = prefs.language as AppLanguage;
      _persistLocal({ language: prefs.language as AppLanguage });
    }
    if (prefs.startScreen && ['HOME', 'FEED', 'EDGE'].includes(prefs.startScreen)) {
      u.startScreen = prefs.startScreen as StartScreen;
    }
    if (typeof prefs.haptics === 'boolean') {
      u.hapticsEnabled = prefs.haptics;
    }
    if (prefs.notificationSettings && typeof prefs.notificationSettings === 'object') {
      u.notificationSettings = { ...get().notificationSettings, ...prefs.notificationSettings };
    }
    set(u as any);
  },
}));

// Listen for system appearance changes
Appearance.addChangeListener(({ colorScheme }) => {
  const store = usePreferencesStore.getState();
  if (store.themeMode === 'system') {
    usePreferencesStore.setState({
      resolvedTheme: colorScheme === 'light' ? 'light' : 'dark',
    });
  }
});

// ★ Hydrate preferences from local storage on app launch
_hydrateFromLocal();
