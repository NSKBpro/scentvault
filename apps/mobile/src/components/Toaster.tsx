/** Renders toasts from the UI store. Mounted once in App.tsx. */
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '../theme/colors';
import { radius, spacing } from '../theme/spacing';
import { useUIStore } from '../stores/ui';

const ICON = { success: 'checkmark-circle', error: 'alert-circle', info: 'information-circle' } as const;
const TINT = { success: colors.success, error: colors.error, info: colors.info } as const;

export function Toaster() {
  const toasts = useUIStore((s) => s.toasts);
  const dismiss = useUIStore((s) => s.dismissToast);
  const insets = useSafeAreaInsets();
  if (!toasts.length) return null;
  return (
    <View pointerEvents="box-none" style={[styles.wrap, { top: insets.top + spacing.sm }]}>
      {toasts.map((t) => (
        <Pressable
          key={t.id}
          onPress={() => dismiss(t.id)}
          style={[styles.toast, { borderLeftColor: TINT[t.type] }]}
          accessibilityRole="alert"
          accessibilityLabel={t.message}
        >
          <Ionicons name={ICON[t.type]} size={18} color={TINT[t.type]} />
          <Text style={styles.text}>{t.message}</Text>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: 'absolute', left: spacing.base, right: spacing.base, zIndex: 1000, gap: spacing.sm },
  toast: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.sm, backgroundColor: colors.card,
    borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, borderLeftWidth: 3,
    paddingVertical: spacing.md, paddingHorizontal: spacing.md,
    shadowColor: '#000', shadowOpacity: 0.4, shadowRadius: 12, shadowOffset: { width: 0, height: 4 }, elevation: 6,
  },
  text: { flex: 1, fontFamily: 'DMSans_500Medium', fontSize: 13, color: colors.text },
});
