import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text } from 'react-native';
import { colors } from '../theme/colors';
import { spacing } from '../theme/spacing';

interface ChipProps {
  label: string;
  active?: boolean;
  onPress?: () => void;
  small?: boolean;
}

export function Chip({ label, active, onPress, small }: ChipProps) {
  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      style={[styles.chip, small && styles.small, active && styles.active]}
      accessibilityRole={onPress ? 'button' : 'text'}
      accessibilityState={{ selected: !!active }}
    >
      <Text style={[styles.text, active && styles.textActive]}>{label}</Text>
    </Pressable>
  );
}

export function ChipRow({ children }: { children: React.ReactNode }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.row}
                contentContainerStyle={styles.rowContent}>
      {children}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  chip: {
    height: 34, paddingHorizontal: 14, borderRadius: 20, backgroundColor: colors.card, borderWidth: 1,
    borderColor: colors.cardBorder, justifyContent: 'center',
  },
  small: { height: 28, paddingHorizontal: 10 },
  active: { backgroundColor: colors.gold, borderColor: colors.gold },
  text: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: colors.textSecondary },
  textActive: { color: colors.background },
  row: { flexGrow: 0, marginBottom: spacing.sm },
  rowContent: { paddingHorizontal: spacing.base, gap: spacing.sm },
});
