/** Inline status banner: offline, pending sync, errors. */
import { Pressable, StyleSheet, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '../theme/colors';
import { radius, spacing } from '../theme/spacing';

type Tone = 'warning' | 'error' | 'info';
const TINT: Record<Tone, string> = { warning: colors.warning, error: colors.error, info: colors.info };
const ICON = { warning: 'cloud-offline-outline', error: 'alert-circle-outline', info: 'information-circle-outline' } as const;

export function Banner({ tone = 'warning', text, onPress }: { tone?: Tone; text: string; onPress?: () => void }) {
  return (
    <Pressable onPress={onPress} disabled={!onPress} accessibilityRole={onPress ? 'button' : 'text'}
               style={[styles.wrap, { backgroundColor: `${TINT[tone]}1A`, borderColor: `${TINT[tone]}40` }]}>
      <Ionicons name={ICON[tone]} size={16} color={TINT[tone]} />
      <Text style={[styles.text, { color: TINT[tone] }]}>{text}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.sm, borderRadius: radius.sm, borderWidth: 1,
    paddingVertical: spacing.sm, paddingHorizontal: spacing.md, marginBottom: spacing.md,
  },
  text: { flex: 1, fontFamily: 'DMSans_500Medium', fontSize: 12 },
});
