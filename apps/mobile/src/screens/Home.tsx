/**
 * Home — today's pick first, then your shelf at a glance.
 *
 *  1. Header + status banners (offline / waiting to sync)
 *  2. Today's pick: occasion chips, top pick with reason chips, two alternates, "Wear this"
 *  3. Onboarding for new users (add 3 bottles → rate → first wear)
 *  4. Stats (owned, spent, avg rating) and Scent DNA (only once there's data)
 *  5. Running low and Shelf time nudges
 *  6. AI advisor search
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import type { CollectionStats, DailyPickOut, PickItem, PickOccasion, ScentDNA, WearOut } from '@api-types';
import { colors } from '../theme/colors';
import { radius, spacing } from '../theme/spacing';
import { api, errorMessage, isNetworkError } from '../lib/api';
import { money, relativeDays } from '../lib/format';
import { useAuthStore } from '../stores/auth';
import { useCollectionStore } from '../stores/collection';
import { useUIStore } from '../stores/ui';
import {
  Banner, BottleGauge, BottleImage, Button, Chip, ChipRow, ReasonChips, ScentDNARadar, Skeleton,
} from '../components';

const OCCASIONS: PickOccasion[] = ['Office', 'Casual', 'Date Night', 'Evening', 'Gym'];
const RUNNING_LOW = 20;
const SHELF_DAYS = 60;

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
}

export function HomeScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const user = useAuthStore((s) => s.user);
  const { items, pending, offline, load, sync, logWear } = useCollectionStore();
  const toast = useUIStore((s) => s.showToast);

  const [stats, setStats] = useState<CollectionStats | null>(null);
  const [dna, setDna] = useState<ScentDNA | null>(null);
  const [pick, setPick] = useState<DailyPickOut | null>(null);
  const [occasion, setOccasionState] = useState<PickOccasion | null>(null);
  const occasionRef = useRef<PickOccasion | null>(null);
  const setOccasion = (o: PickOccasion | null) => { occasionRef.current = o; setOccasionState(o); };
  const [focus, setFocus] = useState(0); // which of the 3 picks is in the spotlight
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [wearing, setWearing] = useState(false);
  const [query, setQuery] = useState('');

  const owned = useMemo(() => items.filter((i) => i.status === 'own'), [items]);

  const fetchPick = useCallback(async (occ: PickOccasion | null) => {
    const { data } = await api.get<DailyPickOut>('/ai/daily-pick', { params: occ ? { occasion: occ } : {} });
    setPick(data);
    setFocus(0);
    if (!occ) { occasionRef.current = data.occasion; setOccasionState(data.occasion); }
  }, []);

  const loadAll = useCallback(async () => {
    setError(null);
    try {
      const [s, d] = await Promise.all([
        api.get<CollectionStats>('/collection/stats'),
        api.get<ScentDNA>('/collection/scent-dna'),
        fetchPick(occasionRef.current),
      ]);
      setStats(s.data);
      setDna(d.data);
    } catch (err) {
      setError(isNetworkError(err) ? 'offline' : errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [fetchPick]);

  useEffect(() => { load(); }, [load]);
  useFocusEffect(useCallback(() => { loadAll(); }, [loadAll]));

  const onRefresh = async () => {
    setRefreshing(true);
    await sync();
    await loadAll();
    setRefreshing(false);
  };

  const chooseOccasion = async (o: PickOccasion) => {
    setOccasion(o);
    try { await fetchPick(o); } catch (err) { toast(errorMessage(err), 'error'); }
  };

  const wear = async (p: PickItem) => {
    setWearing(true);
    try {
      const bottle = owned.find((b) => b.id === p.collection_item_id);
      try {
        await api.post<WearOut>('/ai/daily-pick/accept', {
          collection_item_id: p.collection_item_id, rank: p.rank, occasion: pick?.occasion,
        });
        await sync();
      } catch (err) {
        if (!isNetworkError(err) || !bottle) throw err;
        await logWear(bottle, { occasion: pick?.occasion }); // queued offline
      }
      toast(`Enjoy ${p.fragrance_name} today ✨`, 'success');
      await fetchPick(occasionRef.current).catch(() => undefined);
    } catch (err) {
      toast(errorMessage(err), 'error');
    } finally {
      setWearing(false);
    }
  };

  const search = () => {
    if (!query.trim()) return;
    navigation.navigate('Discover', { screen: 'DiscoverMain', params: { initialQuery: query.trim() } });
    setQuery('');
  };

  const initial = (user?.display_name || user?.email || '?')[0].toUpperCase();
  const isOffline = error === 'offline' || offline;
  const ownedCount = stats?.owned_count ?? owned.length;
  const runningLow = owned.filter((b) => b.remaining_pct <= RUNNING_LOW).sort((a, b) => a.remaining_pct - b.remaining_pct);
  const shelf = owned.filter((b) => {
    const ref = b.last_worn_on ?? b.created_at.slice(0, 10);
    return (Date.now() - new Date(ref).getTime()) / 86_400_000 >= SHELF_DAYS;
  }).slice(0, 3);
  const spotlight = pick?.picks[focus];
  const wornToday = spotlight ? pick?.worn_today.includes(spotlight.collection_item_id) : false;
  const rated = owned.filter((b) => b.rating != null).length;
  const hasWear = owned.some((b) => b.wear_count > 0);

  return (
    <ScrollView
      style={[styles.container, { paddingTop: insets.top }]}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.gold} />}
    >
      {/* Header */}
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={styles.appName}>ScentVault</Text>
          <Text style={styles.subtitle}>{greeting()}{user?.display_name ? `, ${user.display_name}` : ''}</Text>
        </View>
        <Pressable style={styles.avatar} onPress={() => navigation.navigate('Profile')}
                   accessibilityRole="button" accessibilityLabel="Profile and settings">
          <Text style={styles.avatarText}>{initial}</Text>
        </Pressable>
      </View>

      {isOffline && <Banner text="You're offline — showing your saved collection. Changes will sync later." />}
      {pending > 0 && !isOffline && (
        <Banner tone="info" text={`${pending} change${pending > 1 ? 's' : ''} waiting to sync — tap to sync now`} onPress={sync} />
      )}
      {error && error !== 'offline' && <Banner tone="error" text={error} onPress={loadAll} />}

      {/* Today's pick */}
      {loading ? (
        <Skeleton style={{ height: 220, borderRadius: radius.base, marginBottom: spacing.lg }} />
      ) : pick && pick.picks.length > 0 && spotlight ? (
        <View style={styles.section}>
          <View style={styles.sectionHead}>
            <Text style={styles.sectionTitle}>Today's pick</Text>
            {pick.weather ? (
              <Text style={styles.weather}>
                {Math.round(pick.weather.temp_c)}°C · {pick.weather.condition} · {pick.weather.city}
              </Text>
            ) : (
              <Pressable onPress={() => navigation.navigate('Profile')} accessibilityRole="button">
                <Text style={styles.weatherHint}>Add your city for weather-aware picks</Text>
              </Pressable>
            )}
          </View>
          <View style={{ marginHorizontal: -spacing.base }}>
            <ChipRow>
              {OCCASIONS.map((o) => <Chip key={o} label={o} active={occasion === o} onPress={() => chooseOccasion(o)} />)}
            </ChipRow>
          </View>
          <Pressable style={styles.pickCard}
                     onPress={() => navigation.navigate('FragranceDetail', { fragranceId: spotlight.fragrance_id })}
                     accessibilityRole="button" accessibilityLabel={`Open ${spotlight.fragrance_name}`}>
            <View style={styles.pickHeader}>
              <BottleImage uri={spotlight.image_url} brand={spotlight.brand_name} size={56} />
              <View style={{ flex: 1 }}>
                <Text style={styles.pickName} numberOfLines={1}>{spotlight.fragrance_name}</Text>
                <Text style={styles.pickSub} numberOfLines={1}>
                  {spotlight.brand_name} · {spotlight.concentration} · last worn {relativeDays(spotlight.last_worn_on)}
                </Text>
              </View>
            </View>
            <ReasonChips reasons={spotlight.reasons} />
            {focus === 0 && pick.sentence ? <Text style={styles.pickReason}>{pick.sentence}</Text> : null}
            {wornToday ? (
              <View style={styles.worn}>
                <Ionicons name="checkmark-circle" size={18} color={colors.success} />
                <Text style={styles.wornText}>Worn today</Text>
              </View>
            ) : (
              <Button title="Wearing this today" onPress={() => wear(spotlight)} loading={wearing} style={{ marginTop: spacing.md }} />
            )}
          </Pressable>
          {pick.picks.length > 1 && (
            <View style={styles.altRow}>
              {pick.picks.map((p, i) => i === focus ? null : (
                <Pressable key={p.collection_item_id} style={styles.alt} onPress={() => setFocus(i)}
                           accessibilityRole="button" accessibilityLabel={`Show ${p.fragrance_name} instead`}>
                  <Text style={styles.altLabel}>OR</Text>
                  <Text style={styles.altName} numberOfLines={1}>{p.fragrance_name}</Text>
                  <Text style={styles.altSub} numberOfLines={1}>{p.reasons[0]?.label ?? p.brand_name}</Text>
                </Pressable>
              ))}
            </View>
          )}
        </View>
      ) : null}

      {/* Onboarding */}
      {!loading && (ownedCount < 3 || rated === 0 || !hasWear) && (
        <View style={styles.onboard}>
          <Text style={styles.onboardTitle}>Get the most out of ScentVault</Text>
          <Step done={ownedCount >= 3} label={`Add 3 bottles you own (${Math.min(ownedCount, 3)}/3)`}
                onPress={() => navigation.navigate('Collection', { screen: 'AddFragrance' })} />
          <Step done={rated > 0} label="Rate them — recommendations learn from 4★+"
                onPress={() => navigation.navigate('Collection')} />
          <Step done={hasWear} label="Log what you wear — picks avoid repeats"
                onPress={() => navigation.navigate('Diary')} />
        </View>
      )}

      {/* Stats */}
      {ownedCount > 0 && (
        <View style={styles.statsRow}>
          <Stat value={String(ownedCount)} label="OWNED" />
          <Stat value={stats ? money(stats.spent, stats.currency, 0) : '—'} label="SPENT" />
          <Stat value={stats?.avg_rating ? stats.avg_rating.toFixed(1) : '—'} label="AVG RATING" />
        </View>
      )}

      {/* Scent DNA — only once there's something to show */}
      {dna && dna.based_on > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Your Scent DNA</Text>
          <View style={styles.radarCard}>
            <ScentDNARadar data={dna as unknown as Record<string, number>} />
            <Text style={styles.caption}>Based on {dna.based_on} bottle{dna.based_on === 1 ? '' : 's'} you own or tried</Text>
          </View>
        </View>
      )}

      {/* Running low */}
      {runningLow.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Running low</Text>
          {runningLow.map((b) => (
            <Pressable key={b.local_id} style={styles.row}
                       onPress={() => navigation.navigate('FragranceDetail', { fragranceId: b.fragrance_id })}
                       accessibilityRole="button" accessibilityLabel={`${b.fragrance_name}, ${b.remaining_pct}% left`}>
              <BottleGauge remainingPct={b.remaining_pct} />
              <View style={{ flex: 1 }}>
                <Text style={styles.rowName} numberOfLines={1}>{b.fragrance_name}</Text>
                <Text style={styles.rowSub} numberOfLines={1}>{b.brand_name}</Text>
              </View>
              <Text style={styles.lowPct}>{b.remaining_pct}%</Text>
            </Pressable>
          ))}
        </View>
      )}

      {/* Shelf time */}
      {shelf.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Shelf time</Text>
          <Text style={styles.caption}>Not worn in {SHELF_DAYS}+ days — give one a spin?</Text>
          {shelf.map((b) => (
            <Pressable key={b.local_id} style={styles.row}
                       onPress={() => navigation.navigate('FragranceDetail', { fragranceId: b.fragrance_id })}
                       accessibilityRole="button">
              <BottleImage uri={b.image_url} brand={b.brand_name} size={40} />
              <View style={{ flex: 1 }}>
                <Text style={styles.rowName} numberOfLines={1}>{b.fragrance_name}</Text>
                <Text style={styles.rowSub}>Last worn {relativeDays(b.last_worn_on)}</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color={colors.textDark} />
            </Pressable>
          ))}
        </View>
      )}

      {/* AI advisor */}
      <View style={styles.searchCard}>
        <View style={styles.searchHeader}>
          <Ionicons name="sparkles" size={14} color={colors.gold} />
          <Text style={styles.searchLabel}>AI SCENT ADVISOR</Text>
        </View>
        <View style={styles.searchRow}>
          <TextInput style={styles.searchInput} value={query} onChangeText={setQuery}
                     placeholder="Describe your perfect scent…" placeholderTextColor={colors.textMuted}
                     returnKeyType="search" onSubmitEditing={search} accessibilityLabel="Describe a scent to search" />
          <Pressable style={[styles.searchButton, !query.trim() && { opacity: 0.4 }]} onPress={search}
                     disabled={!query.trim()} accessibilityRole="button" accessibilityLabel="Search">
            <Ionicons name="arrow-forward" size={18} color={colors.background} />
          </Pressable>
        </View>
      </View>

      <View style={{ height: spacing['3xl'] }} />
    </ScrollView>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <View style={styles.statCard} accessible accessibilityLabel={`${label.toLowerCase()}: ${value}`}>
      <Text style={styles.statValue} numberOfLines={1} adjustsFontSizeToFit>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function Step({ done, label, onPress }: { done: boolean; label: string; onPress: () => void }) {
  return (
    <Pressable style={styles.step} onPress={onPress} disabled={done} accessibilityRole="button"
               accessibilityState={{ checked: done }}>
      <Ionicons name={done ? 'checkmark-circle' : 'ellipse-outline'} size={20} color={done ? colors.success : colors.gold} />
      <Text style={[styles.stepText, done && styles.stepDone]}>{label}</Text>
      {!done && <Ionicons name="chevron-forward" size={16} color={colors.textDark} />}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingHorizontal: spacing.base },
  header: { flexDirection: 'row', alignItems: 'center', paddingTop: spacing.base, paddingBottom: spacing.lg },
  appName: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 26, color: colors.gold },
  subtitle: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: colors.textMuted, marginTop: 2 },
  avatar: {
    width: 42, height: 42, borderRadius: 21, backgroundColor: colors.card, borderWidth: 1.5, borderColor: colors.gold,
    justifyContent: 'center', alignItems: 'center',
  },
  avatarText: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: colors.gold },
  section: { marginBottom: spacing.lg },
  sectionHead: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: spacing.sm },
  sectionTitle: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 17, color: colors.text, marginBottom: spacing.sm },
  weather: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: colors.textSecondary },
  weatherHint: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: colors.gold },
  pickCard: { backgroundColor: colors.card, borderRadius: radius.base, borderWidth: 1, borderColor: colors.goldDim, padding: spacing.base, gap: spacing.md },
  pickHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  pickName: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 19, color: colors.text },
  pickSub: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: colors.textMuted, marginTop: 2 },
  pickReason: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: colors.textSecondary, lineHeight: 20 },
  worn: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: spacing.sm },
  wornText: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: colors.success },
  altRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm },
  alt: { flex: 1, backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.md },
  altLabel: { fontFamily: 'DMSans_500Medium', fontSize: 10, color: colors.textDark, letterSpacing: 1 },
  altName: { fontFamily: 'DMSans_700Bold', fontSize: 13, color: colors.text, marginTop: 2 },
  altSub: { fontFamily: 'DMSans_400Regular', fontSize: 11, color: colors.textMuted, marginTop: 2 },
  onboard: { backgroundColor: colors.card, borderRadius: radius.base, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.base, marginBottom: spacing.lg, gap: spacing.sm },
  onboardTitle: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 16, color: colors.text, marginBottom: spacing.xs },
  step: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.xs },
  stepText: { flex: 1, fontFamily: 'DMSans_500Medium', fontSize: 13, color: colors.text },
  stepDone: { color: colors.textMuted, textDecorationLine: 'line-through' },
  statsRow: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.lg },
  statCard: { flex: 1, backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, paddingVertical: spacing.md, paddingHorizontal: spacing.sm, alignItems: 'center' },
  statValue: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 20, color: colors.text },
  statLabel: { fontFamily: 'DMSans_500Medium', fontSize: 11, color: colors.textDark, letterSpacing: 1, marginTop: 4 },
  radarCard: { backgroundColor: colors.card, borderRadius: radius.base, borderWidth: 1, borderColor: colors.cardBorder, paddingVertical: spacing.md, alignItems: 'center' },
  caption: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: colors.textMuted, marginBottom: spacing.sm },
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.md, marginBottom: spacing.sm, gap: spacing.md },
  rowName: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: colors.text },
  rowSub: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: colors.textMuted, marginTop: 2 },
  lowPct: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: colors.error },
  searchCard: { backgroundColor: colors.card, borderRadius: radius.base, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.base, marginBottom: spacing.lg },
  searchHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: spacing.md },
  searchLabel: { fontFamily: 'DMSans_500Medium', fontSize: 11, color: colors.gold, letterSpacing: 1.5 },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  searchInput: { flex: 1, backgroundColor: colors.background, borderRadius: radius.sm, borderWidth: 1, borderColor: colors.cardBorder, height: 44, paddingHorizontal: spacing.md, color: colors.text, fontFamily: 'DMSans_400Regular', fontSize: 14 },
  searchButton: { width: 44, height: 44, borderRadius: radius.sm, backgroundColor: colors.gold, justifyContent: 'center', alignItems: 'center' },
});
