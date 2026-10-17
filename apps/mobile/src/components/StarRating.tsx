/** Read-only or editable 5-star rating with half-star display and screen-reader labels. */
import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '../theme/colors';

interface Props {
  value: number | null;
  onChange?: (v: number | null) => void;
  size?: number;
}

export function StarRating({ value, onChange, size = 14 }: Props) {
  const v = value ?? 0;
  const icon = (i: number) => (v >= i ? 'star' : v >= i - 0.5 ? 'star-half' : 'star-outline');
  if (!onChange) {
    return (
      <View style={styles.row} accessible accessibilityLabel={value ? `Rated ${value} of 5` : 'Not rated'}>
        {[1, 2, 3, 4, 5].map((i) => <Ionicons key={i} name={icon(i)} size={size} color={colors.gold} />)}
      </View>
    );
  }
  return (
    <View style={styles.row} accessibilityRole="adjustable" accessibilityLabel={`Rating ${v || 'none'} of 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Pressable
          key={i}
          hitSlop={6}
          onPress={() => onChange(v === i ? (i === 1 ? null : i - 0.5) : i)}
          onLongPress={() => onChange(i - 0.5)}
          accessibilityRole="button"
          accessibilityLabel={`Rate ${i} of 5`}
          style={{ paddingHorizontal: 3 }}
        >
          <Ionicons name={icon(i)} size={size} color={colors.gold} />
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({ row: { flexDirection: 'row', alignItems: 'center' } });
