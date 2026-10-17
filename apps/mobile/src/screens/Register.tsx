/**
 * Register screen.
 */

import { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Button, Input } from '../components';
import { colors, typography, spacing } from '../theme';
import { useAuthStore } from '../stores/auth';

type Props = NativeStackScreenProps<any, 'Register'>;

export function RegisterScreen({ navigation }: Props) {
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const { register, isLoading, error, clearError } = useAuthStore();

  const passwordsMatch = password === confirmPassword;
  const canSubmit = email.trim() && password.length >= 6 && passwordsMatch;

  const handleRegister = async () => {
    if (!canSubmit) return;
    try {
      await register(email.trim(), password, displayName.trim() || undefined);
    } catch {
      // Error set in store
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.header}>
          <Text style={styles.title}>Create Account</Text>
          <Text style={styles.subtitle}>Start your fragrance journey</Text>
        </View>

        <View style={styles.form}>
          <Input
            label="Email"
            value={email}
            onChangeText={(t) => { setEmail(t); clearError(); }}
            placeholder="you@example.com"
            autoCapitalize="none"
            keyboardType="email-address"
            textContentType="emailAddress"
            containerStyle={styles.field}
          />

          <Input
            label="Display Name (optional)"
            value={displayName}
            onChangeText={setDisplayName}
            placeholder="How should we call you?"
            containerStyle={styles.field}
          />

          <Input
            label="Password"
            value={password}
            onChangeText={(t) => { setPassword(t); clearError(); }}
            placeholder="At least 6 characters"
            secureTextEntry
            textContentType="newPassword"
            containerStyle={styles.field}
          />

          <Input
            label="Confirm Password"
            value={confirmPassword}
            onChangeText={setConfirmPassword}
            placeholder="Repeat your password"
            secureTextEntry
            error={confirmPassword && !passwordsMatch ? 'Passwords do not match' : undefined}
            containerStyle={styles.field}
          />

          {error && <Text style={styles.error}>{error}</Text>}

          <Button
            title="Create Account"
            onPress={handleRegister}
            loading={isLoading}
            disabled={!canSubmit}
            style={styles.button}
          />

          <TouchableOpacity
            onPress={() => navigation.goBack()}
            style={styles.switchLink}
          >
            <Text style={styles.switchText}>
              Already have an account?{' '}
              <Text style={styles.switchHighlight}>Sign In</Text>
            </Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  scroll: { flexGrow: 1, justifyContent: 'center', padding: spacing.xl },
  header: { alignItems: 'center', marginBottom: spacing['2xl'] },
  title: { ...typography.h1, color: colors.gold, marginBottom: spacing.xs },
  subtitle: { ...typography.body, color: colors.textMuted },
  form: { gap: spacing.base },
  field: { marginBottom: spacing.xs },
  error: { ...typography.bodySmall, color: colors.error, textAlign: 'center' },
  button: { marginTop: spacing.md },
  switchLink: { alignItems: 'center', marginTop: spacing.lg },
  switchText: { ...typography.body, color: colors.textMuted },
  switchHighlight: { color: colors.gold, fontWeight: '600' },
});
