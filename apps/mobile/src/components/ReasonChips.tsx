import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import type { ReasonChip } from '@api-types';
import { colors } from '../theme/colors';

export function ReasonChips({ reasons, max = 3 }: { reasons: ReasonChip[]; max?: number }) {
  return (
    <View style={styles.row}>
      {reasons.slice(0, max).map((r) => (
        <View key={r.label} style={[styles.chip, r.positive ? styles.pos : styles.neg]}>
          <Text style={[styles.text, { color: r.positive ? colors.gold : colors.textMuted }]}>{r.label}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { borderRadius: 12, paddingHorizontal: 9, paddingVertical: 4, borderWidth: 1 },
  pos: { backgroundColor: colors.goldLight, borderColor: 'rgba(201,169,110,0.35)' },
  neg: { backgroundColor: 'rgba(255,255,255,0.04)', borderColor: colors.cardBorder },
  text: { fontFamily: 'DMSans_500Medium', fontSize: 11 },
});
