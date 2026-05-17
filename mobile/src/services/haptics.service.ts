/**
 * Haptics Service
 * Provides haptic feedback tied to user preferences.
 * Reads `haptics` from preferences store — if disabled, all calls are no-ops.
 */
import * as Haptics from 'expo-haptics';
import { Platform } from 'react-native';
import { usePreferencesStore } from '../stores/preferences.store';

function isEnabled(): boolean {
  return usePreferencesStore.getState().hapticsEnabled;
}

/** Light tap — button presses, toggles */
export function hapticLight() {
  if (!isEnabled() || Platform.OS === 'web') return;
  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
}

/** Medium tap — important actions, card selections */
export function hapticMedium() {
  if (!isEnabled() || Platform.OS === 'web') return;
  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
}

/** Heavy tap — critical actions, errors */
export function hapticHeavy() {
  if (!isEnabled() || Platform.OS === 'web') return;
  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy).catch(() => {});
}

/** Success feedback — confirmations */
export function hapticSuccess() {
  if (!isEnabled() || Platform.OS === 'web') return;
  Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
}

/** Warning feedback — caution alerts */
export function hapticWarning() {
  if (!isEnabled() || Platform.OS === 'web') return;
  Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning).catch(() => {});
}

/** Error feedback — failures */
export function hapticError() {
  if (!isEnabled() || Platform.OS === 'web') return;
  Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error).catch(() => {});
}

/** Selection change — scrolling, picking */
export function hapticSelection() {
  if (!isEnabled() || Platform.OS === 'web') return;
  Haptics.selectionAsync().catch(() => {});
}

/** Notification received — alert vibration pattern */
export function hapticNotification(priority: 'HIGH' | 'MEDIUM' | 'LOW' = 'MEDIUM') {
  if (!isEnabled() || Platform.OS === 'web') return;
  if (priority === 'HIGH') {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning).catch(() => {});
  } else {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
  }
}
