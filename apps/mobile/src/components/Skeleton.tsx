/** Pulsing placeholders shown while data loads (instead of full-screen spinners). */
import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View, type ViewStyle } from 'react-native';
import { colors } from '../theme/colors';
import { radius, spacing } from '../theme/spacing';

export function Skeleton({ style }: { style?: ViewStyle }) {
  const pulse = useRef(new Animated.Value(0.5)).current;
  useEffect(() => {
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: true }),
      Animated.timing(pulse, { toValue: 0.5, duration: 700, useNativeDriver: true }),
    ]));
    loop.start();
    return () => loop.stop();
  }, [pulse]);
  return <Animated.View style={[styles.block, style, { opacity: pulse }]} accessibilityElementsHidden />;
}

export function SkeletonRows({ count = 5, height = 72 }: { count?: number; height?: number }) {
  return (
    <View style={{ gap: spacing.sm }} accessibilityLabel="Loading">
      {Array.from({ length: count }, (_, i) => <Skeleton key={i} style={{ height, borderRadius: radius.md }} />)}
    </View>
  );
}

const styles = StyleSheet.create({ block: { backgroundColor: colors.skeleton, borderRadius: radius.sm } });
