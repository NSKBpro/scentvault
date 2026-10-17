/**
 * Note Pyramid — displays fragrance notes grouped by position.
 *
 * Top notes: warm yellow (#E8C97A)
 * Heart notes: gold (#C9A96E)
 * Base notes: deep amber (#8B6F3A)
 */

import { StyleSheet, Text, View } from 'react-native';
import { colors } from '../theme/colors';
import { spacing, radius } from '../theme/spacing';

interface Note {
  name: string;
  position: 'top' | 'heart' | 'base';
}

interface NotePyramidProps {
  notes: Note[];
}

const LAYERS = [
  { key: 'top', label: 'TOP', color: '#E8C97A' },
  { key: 'heart', label: 'HEART', color: '#C9A96E' },
  { key: 'base', label: 'BASE', color: '#8B6F3A' },
] as const;

export function NotePyramid({ notes }: NotePyramidProps) {
  if (!notes?.length) return null;

  return (
    <View style={styles.card}>
      <Text style={styles.header}>FRAGRANCE PYRAMID</Text>
      {LAYERS.map(({ key, label, color }) => {
        const layerNotes = notes.filter((n) => n.position === key);
        if (layerNotes.length === 0) return null;
        return (
          <View key={key} style={styles.layer}>
            <Text style={[styles.layerLabel, { color }]}>{label}</Text>
            <View style={styles.tags}>
              {layerNotes.map((n) => (
                <View
                  key={n.name}
                  style={[
                    styles.tag,
                    {
                      backgroundColor: `${color}15`,
                      borderColor: `${color}30`,
                    },
                  ]}
                >
                  <Text style={[styles.tagText, { color }]}>{n.name}</Text>
                </View>
              ))}
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.base,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: spacing.base,
    marginBottom: spacing.base,
  },
  header: {
    fontFamily: 'DMSans_500Medium',
    fontSize: 10,
    color: colors.textDark,
    letterSpacing: 1.5,
    marginBottom: spacing.md,
  },
  layer: {
    marginBottom: spacing.md,
  },
  layerLabel: {
    fontFamily: 'DMSans_700Bold',
    fontSize: 10,
    letterSpacing: 1,
    marginBottom: spacing.xs,
  },
  tags: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  tag: {
    borderWidth: 1,
    borderRadius: radius.sm,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  tagText: {
    fontFamily: 'DMSans_400Regular',
    fontSize: 11,
  },
});