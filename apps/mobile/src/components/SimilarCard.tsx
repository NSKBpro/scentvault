/**
 * SimilarCard — card for similar fragrance display.
 * Shows name, brand, and similarity percentage ring.
 */

import { Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { colors } from '../theme/colors';
import { spacing } from '../theme/spacing';

interface SimilarCardProps {
  name: string;
  brand: string;
  similarityPct: number;
  onPress: () => void;
}

export function SimilarCard({ name, brand, similarityPct, onPress }: SimilarCardProps) {
  const SIZE = 48;
  const STROKE = 3;
  const R = (SIZE - STROKE) / 2;
  const CIRC = 2 * Math.PI * R;
  const progress = (similarityPct / 100) * CIRC;

  return (
    <Pressable style={styles.card} onPress={onPress}>
      {/* Similarity ring */}
      <View style={styles.ringContainer}>
        <Svg width={SIZE} height={SIZE}>
          <Circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={R}
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={STROKE}
            fill="none"
          />
          <Circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={R}
            stroke={colors.gold}
            strokeWidth={STROKE}
            fill="none"
            strokeDasharray={`${progress} ${CIRC}`}
            strokeLinecap="round"
            transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
          />
        </Svg>
        <Text style={styles.ringText}>{similarityPct}%</Text>
      </View>

      <Text style={styles.name} numberOfLines={2}>{name}</Text>
      <Text style={styles.brand} numberOfLines={1}>{brand}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    width: 140,
    height: 160,
    backgroundColor: colors.background,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: spacing.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  ringContainer: {
    width: 48,
    height: 48,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  ringText: {
    position: 'absolute',
    fontFamily: 'DMSans_700Bold',
    fontSize: 11,
    color: colors.gold,
  },
  name: {
    fontFamily: 'DMSans_500Medium',
    fontSize: 12,
    color: colors.text,
    textAlign: 'center',
  },
  brand: {
    fontFamily: 'DMSans_400Regular',
    fontSize: 10,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: 2,
  },
});