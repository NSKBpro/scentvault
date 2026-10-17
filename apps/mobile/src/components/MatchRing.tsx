/**
 * MatchRing — circular progress ring for match/similarity percentage.
 * 42x42px with gold fill arc and percentage number in center.
 */

import { StyleSheet, Text, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { colors } from '../theme/colors';

interface MatchRingProps {
  pct: number;
  size?: number;
}

export function MatchRing({ pct, size = 42 }: MatchRingProps) {
  const STROKE = 3;
  const R = (size - STROKE) / 2;
  const CIRC = 2 * Math.PI * R;
  const progress = (Math.min(pct, 100) / 100) * CIRC;

  return (
    <View style={[styles.container, { width: size, height: size }]}>
      <Svg width={size} height={size}>
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={R}
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={STROKE}
          fill="none"
        />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={R}
          stroke={colors.gold}
          strokeWidth={STROKE}
          fill="none"
          strokeDasharray={`${progress} ${CIRC}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </Svg>
      <Text style={styles.text}>{Math.round(pct)}%</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  text: {
    position: 'absolute',
    fontFamily: 'DMSans_700Bold',
    fontSize: 10,
    color: colors.gold,
  },
});