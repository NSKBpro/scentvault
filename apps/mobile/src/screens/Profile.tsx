/**
 * Profile & settings — account, preferences (currency, city for weather, gender filter),
 * notification toggles, sync status, sign out.
 */
import React, { useEffect, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { GenderPreference, PreferencesUpdate } from '@api-types';
import { colors } from '../theme/colors';
import { radius, spacing } from '../theme/spacing';
import { API_URL, errorMessage } from '../lib/api';
import { useAuthStore } from '../stores/auth';
import { useCollectionStore } from '../stores/collection';
import { useUIStore } from '../stores/ui';
import { Banner, Button, Chip } from '../components';

const GENDERS: GenderPreference[] = ['Any', 'Masculine', 'Feminine', 'Unisex'];

export function ProfileScreen() {
  const { user, prefs, meta, updatePrefs, updateProfile, logout, loadPrefs } = useAuthStore();
  const { pending, offline, isSyncing, sync, items } = useCollectionStore();
  const toast = useUIStore((s) => s.showToast);
  const [name, setName] = useState(user?.display_name ?? '');
  const [city, setCity] = useState(prefs?.city ?? '');
  const [savingCity, setSavingCity] = useState(false);
  const [pwOpen, setPwOpen] = useState(false);
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');

  useEffect(() => { loadPrefs(); }, [loadPrefs]);
  useEffect(() => { setCity(prefs?.city ?? ''); }, [prefs?.city]);
  useEffect(() => { setName(user?.display_name ?? ''); }, [user?.display_name]);

  const patch = async (p: PreferencesUpdate, done?: string) => {
    try {
      await updatePrefs(p);
      if (done) toast(done, 'success');
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  };

  const saveCity = async () => {
    setSavingCity(true);
    await patch({ city: city.trim() || null }, city.trim() ? 'City saved — picks now use your weather' : 'City cleared');
    setSavingCity(false);
  };

  const saveName = async () => {
    try {
      await updateProfile({ display_name: name.trim() });
      toast('Name updated', 'success');
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  };

  const changePassword = async () => {
    try {
      await updateProfile({ current_password: currentPw, new_password: newPw });
      toast('Password changed — other devices were signed out', 'success');
      setPwOpen(false);
      setCurrentPw('');
      setNewPw('');
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  };

  const confirmLogout = () => {
    const warn = pending > 0 ? `\n\n${pending} change(s) haven't synced yet and will be lost.` : '';
    Alert.alert('Sign out?', `You'll need your password to sign back in.${warn}`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign out', style: 'destructive', onPress: logout },
    ]);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <View style={styles.hero}>
        <View style={styles.avatar}><Text style={styles.avatarText}>{(user?.display_name || user?.email || '?')[0].toUpperCase()}</Text></View>
        <Text style={styles.email}>{user?.email}</Text>
        <Text style={styles.muted}>{items.filter((i) => i.status === 'own').length} bottles on your shelf</Text>
      </View>

      <Section title="Account">
        <Text style={styles.label}>Display name</Text>
        <View style={styles.row}>
          <TextInput style={[styles.input, { flex: 1 }]} value={name} onChangeText={setName} placeholder="Your name"
                     placeholderTextColor={colors.textDark} accessibilityLabel="Display name" />
          <Button title="Save" onPress={saveName} disabled={name.trim() === (user?.display_name ?? '')} />
        </View>
        {pwOpen ? (
          <View style={{ gap: spacing.sm, marginTop: spacing.md }}>
            <TextInput style={styles.input} value={currentPw} onChangeText={setCurrentPw} secureTextEntry
                       placeholder="Current password" placeholderTextColor={colors.textDark} accessibilityLabel="Current password" />
            <TextInput style={styles.input} value={newPw} onChangeText={setNewPw} secureTextEntry
                       placeholder="New password (8+ characters)" placeholderTextColor={colors.textDark} accessibilityLabel="New password" />
            <Button title="Change password" onPress={changePassword} disabled={!currentPw || newPw.length < 8} />
          </View>
        ) : (
          <Pressable onPress={() => setPwOpen(true)} style={{ marginTop: spacing.md }} accessibilityRole="button">
            <Text style={styles.link}>Change password</Text>
          </Pressable>
        )}
      </Section>

      <Section title="Preferences">
        <Text style={styles.label}>Currency</Text>
        <View style={styles.wrap}>
          {Object.keys(meta.currencies).map((c) => (
            <Chip key={c} label={c} active={prefs?.currency === c} onPress={() => patch({ currency: c })} />
          ))}
        </View>
        <Text style={styles.hint}>Prices you paid stay in their own currency; totals and catalog prices convert.</Text>

        <Text style={styles.label}>City (for weather-aware daily picks)</Text>
        <View style={styles.row}>
          <TextInput style={[styles.input, { flex: 1 }]} value={city} onChangeText={setCity} placeholder="e.g. Novi Sad"
                     placeholderTextColor={colors.textDark} accessibilityLabel="City" returnKeyType="done" onSubmitEditing={saveCity} />
          <Button title="Save" onPress={saveCity} loading={savingCity} disabled={city.trim() === (prefs?.city ?? '')} />
        </View>
        {prefs?.timezone ? <Text style={styles.hint}>Time zone: {prefs.timezone}</Text> : null}

        <Text style={styles.label}>Recommend fragrances marketed as</Text>
        <View style={styles.wrap}>
          {GENDERS.map((g) => (
            <Chip key={g} label={g === 'Any' ? 'Anything' : g} active={prefs?.gender_preference === g}
                  onPress={() => patch({ gender_preference: g })} />
          ))}
        </View>
        <Text style={styles.hint}>Unisex fragrances are always included.</Text>
      </Section>

      <Section title="Notifications">
        <Toggle label="Wishlist price alerts" value={prefs?.notify_price_alerts ?? true}
                onChange={(v) => patch({ notify_price_alerts: v })} />
        <Toggle label="Running low (under 15%)" value={prefs?.notify_running_low ?? true}
                onChange={(v) => patch({ notify_running_low: v })} />
        <Toggle label="Bottles not worn in 60 days" value={prefs?.notify_neglected ?? true}
                onChange={(v) => patch({ notify_neglected: v })} />
      </Section>

      <Section title="Sync">
        {offline ? <Banner text="Offline — your changes are kept on this phone." /> : null}
        <Text style={styles.body}>
          {pending ? `${pending} change${pending > 1 ? 's' : ''} waiting to sync.` : 'Everything is synced.'}
        </Text>
        <Button title={isSyncing ? 'Syncing…' : 'Sync now'} variant="secondary" loading={isSyncing}
                onPress={async () => {
                  const r = await sync();
                  if (r) toast(r.offline ? 'Still offline' : `Synced${r.synced ? ` ${r.synced} change(s)` : ''}`, r.offline ? 'info' : 'success');
                }} style={{ marginTop: spacing.md }} />
        <Text style={styles.hint}>Server: {API_URL}</Text>
      </Section>

      <Pressable onPress={confirmLogout} style={styles.logout} accessibilityRole="button">
        <Ionicons name="log-out-outline" size={18} color={colors.error} />
        <Text style={styles.logoutText}>Sign out</Text>
      </Pressable>
      <View style={{ height: spacing['3xl'] }} />
    </ScrollView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <View style={styles.card}>{children}</View>
    </View>
  );
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <View style={styles.toggle}>
      <Text style={styles.body}>{label}</Text>
      <Switch value={value} onValueChange={onChange} trackColor={{ false: colors.textDark, true: colors.gold }}
              thumbColor={colors.text} accessibilityLabel={label} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingHorizontal: spacing.base },
  hero: { alignItems: 'center', paddingVertical: spacing.xl, gap: 4 },
  avatar: { width: 72, height: 72, borderRadius: 36, borderWidth: 2, borderColor: colors.gold, backgroundColor: colors.card, justifyContent: 'center', alignItems: 'center', marginBottom: spacing.sm },
  avatarText: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 30, color: colors.gold },
  email: { fontFamily: 'DMSans_500Medium', fontSize: 15, color: colors.text },
  muted: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: colors.textMuted },
  section: { marginBottom: spacing.lg },
  sectionTitle: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 17, color: colors.text, marginBottom: spacing.sm },
  card: { backgroundColor: colors.card, borderRadius: radius.base, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.base },
  label: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: colors.textSecondary, marginBottom: spacing.sm, marginTop: spacing.md },
  hint: { fontFamily: 'DMSans_400Regular', fontSize: 11, color: colors.textDark, marginTop: spacing.sm },
  body: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: colors.text, flex: 1 },
  link: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: colors.gold },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  input: { backgroundColor: colors.background, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, height: 46, paddingHorizontal: spacing.md, color: colors.text, fontFamily: 'DMSans_400Regular', fontSize: 14 },
  toggle: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: spacing.sm },
  logout: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.sm, padding: spacing.base },
  logoutText: { fontFamily: 'DMSans_700Bold', fontSize: 15, color: colors.error },
});
