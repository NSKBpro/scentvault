import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '../theme/colors';
import { spacing } from '../theme/spacing';
import { Button } from './Button';

interface Props {
  icon: React.ComponentProps<typeof Ionicons>['name'];
  title: string;
  body?: string;
  action?: { label: string; onPress: () => void };
}

export function EmptyState({ icon, title, body, action }: Props) {
  return (
    <View style={styles.wrap}>
      <Ionicons name={icon} size={44} color={colors.textDark} />
      <Text style={styles.title}>{title}</Text>
      {body ? <Text style={styles.body}>{body}</Text> : null}
      {action ? <Button title={action.label} onPress={action.onPress} style={{ marginTop: spacing.md, paddingHorizontal: spacing.xl }} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', paddingVertical: spacing['2xl'], paddingHorizontal: spacing.xl, gap: spacing.sm },
  title: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 18, color: colors.text, textAlign: 'center' },
  body: { fontFamily: 'DMSans_400Regular', fontSize: 13, lineHeight: 20, color: colors.textMuted, textAlign: 'center' },
});
