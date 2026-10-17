/**
 * Collection — your shelf.
 *
 * Status chips (Owned / Wishlist / Tried / Archive) + family chips, sort menu,
 * one-tap "wear today" on owned bottles, long-press to edit the bottle, FAB to add.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { colors } from '../theme/colors';
import { radius, spacing } from '../theme/spacing';
import { bottleBadge, relativeDays, STATUS_LABEL } from '../lib/format';
import { errorMessage } from '../lib/api';
import type { LocalBottle } from '../lib/offlineDb';
import {
  familiesOf, filterItems, statusCounts, useCollectionStore, type SortOption, type StatusFilter,
} from '../stores/collection';
import { useUIStore } from '../stores/ui';
import {
  Banner, BottleGauge, BottleImage, BottleSheet, Chip, ChipRow, EmptyState, SkeletonRows, StarRating,
} from '../components';

const SORTS: { key: SortOption; label: string }[] = [
  { key: 'date_desc', label: 'Newest' },
  { key: 'alpha', label: 'A → Z' },
  { key: 'rating', label: 'Rating' },
  { key: 'remaining', label: 'Running low' },
  { key: 'last_worn', label: 'Longest unworn' },
];

const STATUS_TABS: { key: StatusFilter; label: string }[] = [
  { key: 'owned', label: 'Owned' },
  { key: 'wishlist', label: 'Wishlist' },
  { key: 'tried', label: 'Tried' },
  { key: 'archive', label: 'Archive' },
];

const EMPTY: Record<StatusFilter, { title: string; body: string }> = {
  owned: { title: 'Your shelf is empty', body: 'Add the bottles you own to get daily picks, stats and recommendations.' },
  wishlist: { title: 'No wishlist yet', body: 'Save fragrances you want and set a price alert to hear when they drop.' },
  tried: { title: 'Nothing tried yet', body: 'Log samples and testers you tried — ratings here teach your recommendations too.' },
  archive: { title: 'Archive is empty', body: 'Finished, sold and gifted bottles end up here with their history.' },
  all: { title: 'Nothing here', body: '' },
};

function Row({ item, onPress, onLongPress, onWear }: {
  item: LocalBottle; onPress: () => void; onLongPress: () => void; onWear: () => void;
}) {
  const badge = bottleBadge(item.bottle_type, item.size_ml);
  const family = item.families[0];
  return (
    <Pressable style={styles.row} onPress={onPress} onLongPress={onLongPress} delayLongPress={300}
               accessibilityRole="button"
               accessibilityLabel={`${item.fragrance_name} by ${item.brand_name}`}
               accessibilityHint="Opens details. Long-press to edit this bottle.">
      <BottleImage uri={item.image_url} brand={item.brand_name} size={52} />
      <View style={styles.rowInfo}>
        <Text style={styles.rowName} numberOfLines={1}>{item.is_favorite ? '♥ ' : ''}{item.fragrance_name}</Text>
        <Text style={styles.rowSub} numberOfLines={1}>{item.brand_name}{family ? ` · ${family}` : ''}</Text>
        <View style={styles.rowMeta}>
          <StarRating value={item.rating} size={12} />
          {badge && <Text style={styles.badge}>{badge}</Text>}
          {item.status === 'own' && item.wear_count > 0 && (
            <Text style={styles.metaText}>worn {relativeDays(item.last_worn_on)}</Text>
          )}
        </View>
      </View>
      {item.status === 'own' ? (
        <View style={styles.right}>
          <View style={styles.gauge}>
            <BottleGauge remainingPct={item.remaining_pct} size={30} />
            <Text style={styles.gaugePct}>{item.remaining_pct}%</Text>
          </View>
          <Pressable onPress={onWear} hitSlop={8} style={styles.wearBtn} accessibilityRole="button"
                     accessibilityLabel={`Wearing ${item.fragrance_name} today`}>
            <Ionicons name="water-outline" size={18} color={colors.gold} />
          </Pressable>
        </View>
      ) : (
        <View style={styles.statusBadge}><Text style={styles.statusText}>{STATUS_LABEL[item.status]}</Text></View>
      )}
      {item.synced === 0 && (
        <Ionicons name="cloud-upload-outline" size={14} color={colors.warning} style={{ marginLeft: 4 }}
                  accessibilityLabel="Waiting to sync" />
      )}
    </Pressable>
  );
}

export function CollectionScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const store = useCollectionStore();
  const { items, isLoading, pending, offline, statusFilter, familyFilter, sortBy } = store;
  const toast = useUIStore((s) => s.showToast);
  const [refreshing, setRefreshing] = useState(false);
  const [showSort, setShowSort] = useState(false);
  const [editing, setEditing] = useState<LocalBottle | null>(null);

  useEffect(() => { store.load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const counts = useMemo(() => statusCounts(items), [items]);
  const inStatus = useMemo(() => filterItems(items, statusFilter, null, sortBy), [items, statusFilter, sortBy]);
  const families = useMemo(() => familiesOf(inStatus), [inStatus]);
  const visible = useMemo(() => filterItems(items, statusFilter, familyFilter, sortBy), [items, statusFilter, familyFilter, sortBy]);

  const onRefresh = async () => {
    setRefreshing(true);
    const res = await store.sync();
    if (res?.conflicts.length) toast(res.conflicts[0], 'info');
    setRefreshing(false);
  };

  const wear = useCallback(async (b: LocalBottle) => {
    try {
      await store.logWear(b);
      toast(`Logged ${b.fragrance_name} for today`, 'success');
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  }, [store, toast]);

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Text style={styles.title}>My Collection</Text>
        <Pressable onPress={() => setShowSort(!showSort)} style={styles.iconBtn}
                   accessibilityRole="button" accessibilityLabel="Sort" accessibilityState={{ expanded: showSort }}>
          <Ionicons name="swap-vertical" size={18} color={colors.textSecondary} />
        </Pressable>
      </View>

      <View style={{ paddingHorizontal: spacing.base }}>
        {offline && <Banner text="Offline — changes are saved on this phone and sync later." />}
        {pending > 0 && !offline && (
          <Banner tone="info" text={`${pending} change${pending > 1 ? 's' : ''} waiting to sync — tap to sync now`}
                  onPress={store.sync} />
        )}
      </View>

      {showSort && (
        <View style={styles.sortMenu}>
          {SORTS.map((o) => (
            <Pressable key={o.key} style={[styles.sortOption, sortBy === o.key && styles.sortActive]}
                       onPress={() => { store.setSort(o.key); setShowSort(false); }}
                       accessibilityRole="menuitem" accessibilityState={{ selected: sortBy === o.key }}>
              <Text style={[styles.sortText, sortBy === o.key && styles.sortTextActive]}>{o.label}</Text>
            </Pressable>
          ))}
        </View>
      )}

      <ChipRow>
        {STATUS_TABS.map((t) => (
          <Chip key={t.key} label={`${t.label} ${counts[t.key]}`} active={statusFilter === t.key}
                onPress={() => store.setStatusFilter(t.key)} />
        ))}
      </ChipRow>
      {families.length > 1 && (
        <ChipRow>
          <Chip small label="All families" active={!familyFilter} onPress={() => store.setFamilyFilter(null)} />
          {families.map((f) => (
            <Chip key={f} small label={f} active={familyFilter === f}
                  onPress={() => store.setFamilyFilter(familyFilter === f ? null : f)} />
          ))}
        </ChipRow>
      )}

      {isLoading && items.length === 0 ? (
        <View style={styles.list}><SkeletonRows count={6} /></View>
      ) : (
        <FlatList
          data={visible}
          keyExtractor={(b) => String(b.local_id)}
          renderItem={({ item }) => (
            <Row item={item}
                 onPress={() => navigation.navigate('FragranceDetail', { fragranceId: item.fragrance_id })}
                 onLongPress={() => setEditing(item)}
                 onWear={() => wear(item)} />
          )}
          contentContainerStyle={[styles.list, { paddingBottom: 110 }]}
          ListEmptyComponent={
            <EmptyState icon="flask-outline" title={EMPTY[statusFilter].title} body={EMPTY[statusFilter].body}
                        action={statusFilter === 'archive' ? undefined
                          : { label: 'Add a fragrance', onPress: () => navigation.navigate('AddFragrance') }} />
          }
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.gold} />}
          initialNumToRender={15}
        />
      )}

      <Pressable style={[styles.fab, { bottom: insets.bottom + 20 }]} onPress={() => navigation.navigate('AddFragrance')}
                 accessibilityRole="button" accessibilityLabel="Add a fragrance">
        <Ionicons name="add" size={28} color={colors.background} />
      </Pressable>

      <BottleSheet bottle={editing} onClose={() => setEditing(null)} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: spacing.base, paddingTop: spacing.base, paddingBottom: spacing.md },
  title: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 24, color: colors.text },
  iconBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.card, justifyContent: 'center', alignItems: 'center' },
  sortMenu: { marginHorizontal: spacing.base, marginBottom: spacing.sm, backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, overflow: 'hidden' },
  sortOption: { paddingVertical: spacing.md, paddingHorizontal: spacing.base, borderBottomWidth: 1, borderBottomColor: colors.cardBorder },
  sortActive: { backgroundColor: colors.goldLight },
  sortText: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: colors.textSecondary },
  sortTextActive: { color: colors.gold, fontFamily: 'DMSans_500Medium' },
  list: { paddingHorizontal: spacing.base, paddingTop: spacing.xs },
  row: { flexDirection: 'row', alignItems: 'center', minHeight: 78, backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, paddingHorizontal: spacing.md, paddingVertical: spacing.sm, marginBottom: spacing.sm, gap: spacing.md },
  rowInfo: { flex: 1 },
  rowName: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: colors.text },
  rowSub: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: colors.textMuted, marginTop: 2 },
  rowMeta: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: 4, flexWrap: 'wrap' },
  metaText: { fontFamily: 'DMSans_400Regular', fontSize: 11, color: colors.textDark },
  badge: { fontFamily: 'DMSans_500Medium', fontSize: 10, color: colors.info, backgroundColor: 'rgba(94,165,224,0.12)', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6, overflow: 'hidden' },
  right: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  gauge: { alignItems: 'center' },
  gaugePct: { fontFamily: 'DMSans_500Medium', fontSize: 11, color: colors.textMuted, marginTop: 2 },
  wearBtn: { width: 36, height: 36, borderRadius: 18, borderWidth: 1, borderColor: colors.goldDim, justifyContent: 'center', alignItems: 'center' },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10, backgroundColor: 'rgba(255,255,255,0.06)' },
  statusText: { fontFamily: 'DMSans_500Medium', fontSize: 11, color: colors.textSecondary },
  fab: { position: 'absolute', right: 20, width: 56, height: 56, borderRadius: 28, backgroundColor: colors.gold, justifyContent: 'center', alignItems: 'center', shadowColor: colors.gold, shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.3, shadowRadius: 12, elevation: 8 },
});
