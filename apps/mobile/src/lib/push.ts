/**
 * Expo push registration. Best effort: simulators, Expo Go without a project id,
 * or a denied permission simply mean no push (in-app notifications still work).
 */
import { Platform } from 'react-native';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';
import { api } from './api';

let currentToken: string | null = null;

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

export async function registerForPush(): Promise<string | null> {
  if (!Device.isDevice) return null;
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'ScentVault',
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  }
  const existing = await Notifications.getPermissionsAsync();
  let status = existing.status;
  if (status !== 'granted') status = (await Notifications.requestPermissionsAsync()).status;
  if (status !== 'granted') return null;
  const projectId =
    (Constants.expoConfig?.extra as { eas?: { projectId?: string } } | undefined)?.eas?.projectId ??
    Constants.easConfig?.projectId;
  try {
    const token = (await Notifications.getExpoPushTokenAsync(projectId ? { projectId } : undefined)).data;
    currentToken = token;
    await api.post('/me/devices', { expo_push_token: token, platform: Platform.OS });
    return token;
  } catch {
    return null; // e.g. Expo Go without an EAS project id
  }
}

export async function unregisterPush(): Promise<void> {
  if (!currentToken) return;
  await api.delete('/me/devices', { params: { token: currentToken } });
  currentToken = null;
}

/** Call with a navigation callback to open the right screen when a push is tapped. */
export function onNotificationTap(handler: (data: Record<string, unknown>) => void): () => void {
  const sub = Notifications.addNotificationResponseReceivedListener((r) => {
    handler((r.notification.request.content.data ?? {}) as Record<string, unknown>);
  });
  return () => sub.remove();
}
