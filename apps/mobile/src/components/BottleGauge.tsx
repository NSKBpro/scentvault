/**
 * BottleGauge — visual indicator of remaining fragrance level.
 */

import React from 'react';
import { StyleSheet, View } from 'react-native';
import { colors } from '../theme/colors';

interface BottleGaugeProps {
  remainingPct: number;
  size?: number;
}

export function BottleGauge({ remainingPct, size = 36 }: BottleGaugeProps) {
  const clamped = Math.max(0, Math.min(100, remainingPct));
  const fillHeight = (clamped / 100) * (size * 0.7);

  const fillColor =
    clamped > 60 ? colors.success :
    clamped > 30 ? colors.gold :
    colors.error;

  return (
    <View style={[styles.container, { width: size * 0.5, height: size }]}>
      <View style={[styles.neck, { width: size * 0.2, height: size * 0.15 }]} />
      <View style={[styles.body, { width: size * 0.5, height: size * 0.7 }]}>
        <View style={[styles.fill, { height: fillHeight, backgroundColor: fillColor }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: 'center' },
  neck: {
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderTopLeftRadius: 3,
    borderTopRightRadius: 3,
    borderWidth: 1,
    borderColor: colors.textDark,
  },
  body: {
    borderWidth: 1,
    borderColor: colors.textDark,
    borderBottomLeftRadius: 4,
    borderBottomRightRadius: 4,
    overflow: 'hidden',
    justifyContent: 'flex-end',
  },
  fill: {
    width: '100%',
    borderBottomLeftRadius: 3,
    borderBottomRightRadius: 3,
  },
});
