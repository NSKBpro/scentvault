/**
 * Diary — the wear log (scent of the day).
 *
 * Calendar with a dot per fragrance worn, the selected day's entries, a quick
 * "log a wear" picker (sprays, compliment), and stats: most worn, shelf time,
 * rotation spread, real cost per wear.
 */
import React, { useCallback, useMemo, useState } from 'react';
import { Alert, Modal, Pressable, RefreshControl, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import type { WearStats } from '@api-types';
import { colors } from '../theme/colors';
import { radius, spacing } from '../theme/spacing';
import { api, errorMessage, isNetworkError } from '../lib/api';
import { money, relativeDays, shortDate, todayISO } from '../lib/format';
import type { LocalBottle, LocalWear } from '../lib/offlineDb';
import { useCollectionStore } from '../stores/collection';
import { useUIStore } from '../stores/ui';
import { Banner, BottleImage, Button, Chip, EmptyState, Skeleton, WearCalendar, dotColor } from '../components';

export function DiaryScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const { items, wears, sync, logWear, removeWear } = useCollectionStore();
  const toast = useUIStore((s) => s.showToast);
  const now = new Date();
  const [ym, setYm] = useState({ y: now.getFullYear(), m: now.getMonth() });
  const [selected, setSelected] = useState<string>(todayISO());
  const [stats, setStats] = useState<WearStats | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [picker, setPicker] = useState(false);

  const owned = useMemo(() => items.filter((i) => i.status === 'own'), [items]);

  const loadStats = useCallback(async () => {
    try {
      const { data } = await api.get<WearStats>('/wears/stats');
      setStats(data);
      setStatsError(null);
    } catch (err) {
      setStatsError(isNetworkError(err) ? 'offline' : errorMessage(err));
    }
  }, []);

  useFocusEffect(useCallback(() => { loadStats(); }, [loadStats]));

  const onRefresh = async () => {
    setRefreshing(true);
    await sync();
    await loadStats();
    setRefreshing(false);
  };

  const shift = (d: number) => setYm(({ y, m }) => {
    const n = new Date(y, m + d, 1);
    return { y: n.getFullYear(), m: n.getMonth() };
  });

  const dayWears = wears.filter((w) => w.worn_on === selected);
  const isFuture = selected > todayISO();

  const confirmDelete = (w: LocalWear) => Alert.alert('Delete this wear?', `${w.fragrance_name} on ${shortDate(w.worn_on)}`, [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Delete', style: 'destructive', onPress: async () => {
      try { await removeWear(w); await loadStats(); } catch (err) { toast(errorMessage(err), 'error'); }
    } },
  ]);

  const log = async (b: LocalBottle, sprays: number | null, compliment: boolean) => {
    setPicker(false);
    try {
      await logWear(b, { worn_on: selected, sprays, compliment });
      toast(`Logged ${b.fragrance_name}${selected === todayISO() ? ' for today' : ` on ${shortDate(selected)}`}`, 'success');
      loadStats();
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  };

  const maxMonth = Math.max(1, ...(stats?.per_month.map((m) => m.wears) ?? [1]));

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Text style={styles.title}>Diary</Text>
        <Pressable style={styles.logBtn} onPress={() => setPicker(true)} disabled={!owned.length || isFuture}
                   accessibilityRole="button" accessibilityLabel="Log a wear">
          <Ionicons name="add" size={18} color={colors.background} />
          <Text style={styles.logText}>Log a wear</Text>
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={styles.content}
                  refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.gold} />}>
        {!owned.length ? (
          <EmptyState icon="calendar-outline" title="Your diary starts with your shelf"
                      body="Add the bottles you own, then log what you wear each day — picks will stop repeating and cost per wear becomes real."
                      action={{ label: 'Add a fragrance', onPress: () => navigation.navigate('Collection', { screen: 'AddFragrance' }) }} />
        ) : (
          <>
            <WearCalendar year={ym.y} month={ym.m} wears={wears} selected={selected} onSelect={setSelected}
                          onPrev={() => shift(-1)} onNext={() => shift(1)} />

            <View style={styles.section}>
              <Text style={styles.sectionTitle}>{selected === todayISO() ? 'Today' : shortDate(selected)}</Text>
              {dayWears.length === 0 ? (
                <Text style={styles.muted}>{isFuture ? 'In the future.' : 'Nothing logged.'}</Text>
              ) : dayWears.map((w) => (
                <Pressable key={`${w.local_id}`} style={styles.wear} onLongPress={() => confirmDelete(w)}
                           onPress={() => navigation.navigate('FragranceDetail', { fragranceId: w.fragrance_id })}
                           accessibilityRole="button" accessibilityHint="Long-press to delete">
                  <View style={[styles.dot, { backgroundColor: dotColor(w.fragrance_id) }]} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.wearName}>{w.fragrance_name}</Text>
                    <Text style={styles.wearSub}>
                      {w.brand_name}
                      {w.sprays ? ` · ${w.sprays} sprays` : ''}
                      {w.occasion ? ` · ${w.occasion}` : ''}
                      {w.temp_c != null ? ` · ${Math.round(w.temp_c)}°C` : ''}
                      {w.compliment ? ' · 💬 compliment' : ''}
                    </Text>
                  </View>
                  {w.synced === 0 && <Ionicons name="cloud-upload-outline" size={14} color={colors.warning} />}
                  <Pressable onPress={() => confirmDelete(w)} hitSlop={8} accessibilityRole="button" accessibilityLabel="Delete wear">
                    <Ionicons name="trash-outline" size={16} color={colors.textDark} />
                  </Pressable>
                </Pressable>
              ))}
            </View>

            {statsError === 'offline' && <Banner text="Stats need a connection — your log is saved and will sync." />}
            {statsError && statsError !== 'offline' && <Banner tone="error" text={statsError} onPress={loadStats} />}

            {!stats && !statsError ? <Skeleton style={{ height: 160, borderRadius: radius.base }} /> : null}
            {stats && (
              <>
                <View style={styles.statsRow}>
                  <Stat value={String(stats.total_wears)} label="WEARS" />
                  <Stat value={String(stats.distinct_fragrances)} label="BOTTLES WORN" />
                  <Stat value={`${Math.round(stats.rotation_spread * 100)}%`} label="ROTATION" />
                  <Stat value={String(stats.compliments)} label="COMPLIMENTS" />
                </View>
                <Text style={styles.hint}>Rotation = how evenly you wore your shelf in the last 90 days.</Text>

                {stats.total_wears > 0 && (
                  <View style={styles.section}>
                    <Text style={styles.sectionTitle}>Wears per month</Text>
                    <View style={styles.bars} accessible accessibilityLabel={stats.per_month.map((m) => `${m.month}: ${m.wears}`).join(', ')}>
                      {stats.per_month.map((m) => (
                        <View key={m.month} style={styles.barCol}>
                          <View style={[styles.bar, { height: 4 + (m.wears / maxMonth) * 70 }]} />
                          <Text style={styles.barLabel}>{m.month.slice(5)}</Text>
                        </View>
                      ))}
                    </View>
                  </View>
                )}

                {stats.most_worn.length > 0 && (
                  <View style={styles.section}>
                    <Text style={styles.sectionTitle}>Most worn</Text>
                    {stats.most_worn.map((b) => (
                      <View key={b.collection_item_id} style={styles.statRow}>
                        <Text style={styles.statName} numberOfLines={1}>{b.fragrance_name}</Text>
                        <Text style={styles.statVal}>
                          {b.wear_count}×{b.cost_per_wear != null ? ` · ${b.cost_per_wear_is_estimate ? '~' : ''}${money(b.cost_per_wear, b.currency)}/wear` : ''}
                        </Text>
                      </View>
                    ))}
                  </View>
                )}

                {stats.shelf_time.length > 0 && (
                  <View style={styles.section}>
                    <Text style={styles.sectionTitle}>Shelf time</Text>
                    <Text style={styles.muted}>Bottles you haven't reached for in a while.</Text>
                    {stats.shelf_time.map((b) => (
                      <Pressable key={b.collection_item_id} style={styles.statRow}
                                 onPress={() => navigation.navigate('FragranceDetail', { fragranceId: b.fragrance_id })}>
                        <Text style={styles.statName} numberOfLines={1}>{b.fragrance_name}</Text>
                        <Text style={styles.statVal}>{b.last_worn_on ? relativeDays(b.last_worn_on) : 'never worn'}</Text>
                      </Pressable>
                    ))}
                  </View>
                )}
              </>
            )}
          </>
        )}
        <View style={{ height: spacing['3xl'] }} />
      </ScrollView>

      <WearPicker visible={picker} bottles={owned} date={selected} onClose={() => setPicker(false)} onPick={log} />
    </View>
  );
}

function WearPicker({ visible, bottles, date, onClose, onPick }: {
  visible: boolean; bottles: LocalBottle[]; date: string; onClose: () => void;
  onPick: (b: LocalBottle, sprays: number | null, compliment: boolean) => void;
}) {
  const insets = useSafeAreaInsets();
  const [sprays, setSprays] = useState<number | null>(null);
  const [compliment, setCompliment] = useState(false);
  const sorted = [...bottles].sort((a, b) => (a.last_worn_on ?? '').localeCompare(b.last_worn_on ?? ''));
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.overlay}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="Close" />
        <View style={[styles.sheet, { paddingBottom: insets.bottom + spacing.base }]}>
          <View style={styles.sheetHead}>
            <Text style={styles.sheetTitle}>What are you wearing{date === todayISO() ? ' today' : ` on ${shortDate(date)}`}?</Text>
            <Pressable onPress={onClose} hitSlop={10} accessibilityRole="button" accessibilityLabel="Close">
              <Ionicons name="close" size={22} color={colors.textSecondary} />
            </Pressable>
          </View>
          <Text style={styles.label}>Sprays (optional — lowers the bottle level by ~0.1 ml each)</Text>
          <View style={styles.wrap}>
            {[2, 4, 6, 8].map((n) => <Chip key={n} small label={`${n}`} active={sprays === n} onPress={() => setSprays(sprays === n ? null : n)} />)}
          </View>
          <View style={styles.switchRow}>
            <Text style={styles.switchLabel}>Got a compliment</Text>
            <Switch value={compliment} onValueChange={setCompliment} trackColor={{ false: colors.textDark, true: colors.gold }} thumbColor={colors.text} />
          </View>
          <ScrollView style={{ maxHeight: 360 }}>
            {sorted.map((b) => (
              <Pressable key={b.local_id} style={styles.pickRow} onPress={() => onPick(b, sprays, compliment)}
                         accessibilityRole="button" accessibilityLabel={`Log ${b.fragrance_name}`}>
                <BottleImage uri={b.image_url} brand={b.brand_name} size={40} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.wearName} numberOfLines={1}>{b.fragrance_name}</Text>
                  <Text style={styles.wearSub}>{b.brand_name} · last worn {relativeDays(b.last_worn_on)}</Text>
                </View>
                <Ionicons name="add-circle-outline" size={22} color={colors.gold} />
              </Pressable>
            ))}
          </ScrollView>
          <Button title="Cancel" variant="secondary" onPress={onClose} style={{ marginTop: spacing.md }} />
        </View>
      </View>
    </Modal>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <View style={styles.statCard} accessible accessibilityLabel={`${label.toLowerCase()}: ${value}`}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.base, paddingTop: spacing.base, paddingBottom: spacing.md },
  title: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 24, color: colors.text },
  logBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: colors.gold, borderRadius: radius.full, paddingHorizontal: spacing.base, height: 38 },
  logText: { fontFamily: 'DMSans_700Bold', fontSize: 13, color: colors.background },
  content: { paddingHorizontal: spacing.base },
  section: { marginTop: spacing.lg },
  sectionTitle: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 17, color: colors.text, marginBottom: spacing.sm },
  muted: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: colors.textMuted, marginBottom: spacing.sm },
  hint: { fontFamily: 'DMSans_400Regular', fontSize: 11, color: colors.textDark, marginTop: spacing.sm },
  wear: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.md, marginBottom: spacing.sm },
  dot: { width: 10, height: 10, borderRadius: 5 },
  wearName: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: colors.text },
  wearSub: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: colors.textMuted, marginTop: 2 },
  statsRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.lg },
  statCard: { flex: 1, backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, paddingVertical: spacing.md, alignItems: 'center' },
  statValue: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 18, color: colors.text },
  statLabel: { fontFamily: 'DMSans_500Medium', fontSize: 10, color: colors.textDark, letterSpacing: 0.8, marginTop: 4, textAlign: 'center' },
  bars: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', height: 100, backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.sm },
  barCol: { alignItems: 'center', flex: 1 },
  bar: { width: 10, borderRadius: 3, backgroundColor: colors.gold },
  barLabel: { fontFamily: 'DMSans_400Regular', fontSize: 10, color: colors.textDark, marginTop: 4 },
  statRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.cardBorder, gap: spacing.md },
  statName: { flex: 1, fontFamily: 'DMSans_500Medium', fontSize: 14, color: colors.text },
  statVal: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: colors.textSecondary },
  overlay: { flex: 1, backgroundColor: colors.overlay, justifyContent: 'flex-end' },
  sheet: { backgroundColor: colors.card, borderTopLeftRadius: radius.xl, borderTopRightRadius: radius.xl, padding: spacing.lg, borderTopWidth: 1, borderColor: colors.cardBorder },
  sheetHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
  sheetTitle: { flex: 1, fontFamily: 'PlayfairDisplay_700Bold', fontSize: 18, color: colors.text },
  label: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: colors.textSecondary, marginTop: spacing.base, marginBottom: spacing.sm },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  switchRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginVertical: spacing.md },
  switchLabel: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: colors.text },
  pickRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingVertical: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.cardBorder },
});
