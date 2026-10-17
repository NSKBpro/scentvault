/** Month calendar with one coloured dot per fragrance worn that day. */
import React, { useMemo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { WearOut } from '@api-types';
import { colors } from '../theme/colors';
import { radius, spacing } from '../theme/spacing';

const DOT_COLORS = ['#C9A96E', '#6ECF8E', '#5EA5E0', '#E0A855', '#C77DDB', '#E07A7A', '#7AD3D3', '#B5C26A'];
const WEEKDAYS = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

/** Stable colour per fragrance so a bottle keeps its dot colour month to month. */
export function dotColor(fragranceId: number): string {
  return DOT_COLORS[fragranceId % DOT_COLORS.length];
}

interface Props {
  year: number;
  month: number; // 0-11
  wears: WearOut[];
  selected: string | null;
  onSelect: (iso: string) => void;
  onPrev: () => void;
  onNext: () => void;
}

export function WearCalendar({ year, month, wears, selected, onSelect, onPrev, onNext }: Props) {
  const byDay = useMemo(() => {
    const m = new Map<string, WearOut[]>();
    for (const w of wears) m.set(w.worn_on, [...(m.get(w.worn_on) ?? []), w]);
    return m;
  }, [wears]);

  const first = new Date(year, month, 1);
  const offset = (first.getDay() + 6) % 7; // Monday first
  const days = new Date(year, month + 1, 0).getDate();
  const cells: (number | null)[] = [...Array(offset).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)];
  while (cells.length % 7) cells.push(null);
  const today = new Date();
  const iso = (d: number) => `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
  const title = first.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });

  return (
    <View style={styles.card}>
      <View style={styles.head}>
        <Pressable onPress={onPrev} hitSlop={10} accessibilityRole="button" accessibilityLabel="Previous month">
          <Ionicons name="chevron-back" size={20} color={colors.textSecondary} />
        </Pressable>
        <Text style={styles.title}>{title}</Text>
        <Pressable onPress={onNext} hitSlop={10} accessibilityRole="button" accessibilityLabel="Next month">
          <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
        </Pressable>
      </View>
      <View style={styles.grid}>
        {WEEKDAYS.map((d, i) => <Text key={i} style={styles.weekday}>{d}</Text>)}
        {cells.map((d, i) => {
          if (d === null) return <View key={i} style={styles.cell} />;
          const key = iso(d);
          const worn = byDay.get(key) ?? [];
          const isToday = d === today.getDate() && month === today.getMonth() && year === today.getFullYear();
          const isSel = selected === key;
          return (
            <Pressable key={i} style={[styles.cell, isSel && styles.selected]} onPress={() => onSelect(key)}
                       accessibilityRole="button"
                       accessibilityLabel={`${key}: ${worn.length ? worn.map((w) => w.fragrance_name).join(', ') : 'nothing logged'}`}>
              <Text style={[styles.day, isToday && styles.today]}>{d}</Text>
              <View style={styles.dots}>
                {worn.slice(0, 3).map((w) => (
                  <View key={`${w.id}-${w.client_ref}`} style={[styles.dot, { backgroundColor: dotColor(w.fragrance_id) }]} />
                ))}
              </View>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.card, borderRadius: radius.base, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.md },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.sm },
  title: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 16, color: colors.text },
  grid: { flexDirection: 'row', flexWrap: 'wrap' },
  weekday: { width: `${100 / 7}%`, textAlign: 'center', fontFamily: 'DMSans_500Medium', fontSize: 11, color: colors.textDark, marginBottom: 4 },
  cell: { width: `${100 / 7}%`, aspectRatio: 1, alignItems: 'center', justifyContent: 'center', borderRadius: radius.sm },
  selected: { backgroundColor: colors.goldLight },
  day: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: colors.textSecondary },
  today: { color: colors.gold, fontFamily: 'DMSans_700Bold' },
  dots: { flexDirection: 'row', gap: 2, height: 6, marginTop: 2 },
  dot: { width: 5, height: 5, borderRadius: 3 },
});
