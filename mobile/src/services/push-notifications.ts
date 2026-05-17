/**
 * FOMO Push Notification Service
 * 
 * Handles:
 * - Permission requests
 * - Expo Push Token registration
 * - Deep link routing from notifications
 * - Background notification handling
 */
import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants from 'expo-constants';
import { mobileApi } from '../services/api/mobile-api';

// Configure how notifications appear when app is in foreground
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
    priority: Notifications.AndroidNotificationPriority.HIGH,
  }),
});

/**
 * Request push notification permissions and register token with backend
 */
export async function registerForPushNotifications(): Promise<string | null> {
  // Push only works on physical devices
  if (Platform.OS === 'web') {
    console.log('[Push] Web platform — skipping push registration');
    return null;
  }

  if (!Device.isDevice) {
    console.log('[Push] Not a physical device — skipping push registration');
    return null;
  }

  try {
    // Check existing permissions
    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;

    // Request if not already granted
    if (existingStatus !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }

    if (finalStatus !== 'granted') {
      console.log('[Push] Permission not granted');
      return null;
    }

    // Get Expo Push Token
    const projectId = Constants.expoConfig?.extra?.eas?.projectId;
    const tokenResult = await Notifications.getExpoPushTokenAsync({
      projectId: projectId || undefined,
    });
    const pushToken = tokenResult.data;

    console.log('[Push] Token obtained:', pushToken);

    // Register with backend
    const platform = Platform.OS === 'ios' ? 'ios' : 'android';
    await mobileApi.registerPushToken(pushToken, platform);

    console.log('[Push] Token registered with backend');
    return pushToken;

  } catch (error) {
    console.error('[Push] Registration error:', error);
    return null;
  }
}

/**
 * Set up Android notification channel (required for Android 8+)
 */
export async function setupAndroidChannel() {
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('signals', {
      name: 'Signal Alerts',
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#4DA3FF',
      sound: 'default',
    });
  }
}

/**
 * Handle notification deep linking
 */
export type PushNavigationHandler = (screen: string, params: Record<string, unknown>) => void;

let navigationHandler: PushNavigationHandler | null = null;

export function setNavigationHandler(handler: PushNavigationHandler) {
  navigationHandler = handler;
}

/**
 * Set up notification listeners (call once in app root)
 */
export function setupNotificationListeners() {
  // Handle notification taps (when user opens app from notification)
  const responseSubscription = Notifications.addNotificationResponseReceivedListener(
    (response) => {
      const data = response.notification.request.content.data as Record<string, unknown>;
      console.log('[Push] Notification opened:', data);

      // Track open with backend
      const notificationId = response.notification.request.identifier;
      mobileApi.trackPushOpened(notificationId, data).catch(() => {});

      // Route to the correct screen
      if (navigationHandler) {
        const screen = (data?.screen as string) || 'home';
        navigationHandler(screen, data);
      }
    }
  );

  // Handle notifications received while app is in foreground
  const notificationSubscription = Notifications.addNotificationReceivedListener(
    (notification) => {
      console.log('[Push] Notification received in foreground:', notification.request.content);
    }
  );

  // Return cleanup function
  return () => {
    responseSubscription.remove();
    notificationSubscription.remove();
  };
}
