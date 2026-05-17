import { Platform } from 'react-native';

const ACCESS_KEY = 'fomo_access_token';
const REFRESH_KEY = 'fomo_refresh_token';

let SecureStore: any = null;

async function getSecureStore() {
  if (SecureStore) return SecureStore;
  if (Platform.OS === 'web') return null;
  try {
    SecureStore = await import('expo-secure-store');
    return SecureStore;
  } catch {
    return null;
  }
}

// Fallback for web: in-memory storage
const memoryStore: Record<string, string> = {};

export const tokenStorage = {
  async set(accessToken: string, refreshToken: string) {
    const store = await getSecureStore();
    if (store) {
      await store.setItemAsync(ACCESS_KEY, accessToken);
      await store.setItemAsync(REFRESH_KEY, refreshToken);
    } else {
      memoryStore[ACCESS_KEY] = accessToken;
      memoryStore[REFRESH_KEY] = refreshToken;
    }
  },

  async get(): Promise<{ accessToken: string | null; refreshToken: string | null }> {
    const store = await getSecureStore();
    if (store) {
      const accessToken = await store.getItemAsync(ACCESS_KEY);
      const refreshToken = await store.getItemAsync(REFRESH_KEY);
      return { accessToken, refreshToken };
    }
    return {
      accessToken: memoryStore[ACCESS_KEY] || null,
      refreshToken: memoryStore[REFRESH_KEY] || null,
    };
  },

  async clear() {
    const store = await getSecureStore();
    if (store) {
      await store.deleteItemAsync(ACCESS_KEY);
      await store.deleteItemAsync(REFRESH_KEY);
    } else {
      delete memoryStore[ACCESS_KEY];
      delete memoryStore[REFRESH_KEY];
    }
  },
};
