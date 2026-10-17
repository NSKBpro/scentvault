/**
 * Fragrance detail.
 *
 *  1. Header (bottle image, name, brand, reference price in your currency)
 *  2. Your bottles — every entry you have for this fragrance (sizes, decants…), each editable
 *  3. Add / wishlist / price alert actions
 *  4. Pyramid, facts, cost per wear
 *  5. Prices per size (public price history)
 *  6. Similar fragrances and cheaper alternatives (compared per ml)
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { AlertOut, DupeItem, FragranceDetail, FragranceMatch, PriceHistoryOut } from '@api-types';
import { colors } from '../theme/colors';
import { radius, spacing } from '../theme/spacing';
import { api, errorMessage } from '../lib/api';
import { BOTTLE_LABEL, STATUS_LABEL, fromUsd, money, relativeDays } from '../lib/format';
import type { LocalBottle } from '../lib/offlineDb';
import { useAuthStore, useCurrency } from '../stores/auth';
import { useCollectionStore } from '../stores/collection';
import { useUIStore } from '../stores/ui';
import {
  BottleGauge, BottleImage, BottleSheet, Button, Chip, EmptyState, NotePyramid, PriceHistory, SimilarCard,
  Skeleton, StarRating,
} from '../components';

const EST_ML_PER_WEAR = 0.4; // ~4 sprays × 0.1 ml — labelled as an estimate
const MIN_REAL_WEARS = 5;

export function FragranceDetailScreen() {
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const fragranceId: number = route.params?.fragranceId;
  const currency = useCurrency();
  const rates = useAuthStore((s) => s.meta.currencies);
  const rate = rates[currency] ?? 1;
  const { items, add, logWear } = useCollectionStore();
  const toast = useUIStore((s) => s.showToast);

  const [fragrance, setFragrance] = useState<FragranceDetail | null>(null);
  const [similar, setSimilar] = useState<FragranceMatch[]>([]);
  const [dupes, setDupes] = useState<DupeItem[]>([]);
  const [history, setHistory] = useState<PriceHistoryOut | null>(null);
  const [alerts, setAlerts] = useState<AlertOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editing, setEditing] = useState<LocalBottle | null>(null);
  const [busy, setBusy] = useState(false);
  const [alertOpen, setAlertOpen] = useState(false);
  const [target, setTarget] = useState('');
  const [alertSize, setAlertSize] = useState<number | null>(null);

  const mine = useMemo(() => items.filter((i) => i.fragrance_id === fragranceId), [items, fragranceId]);
  const owned = mine.filter((b) => b.status === 'own');
  const alert = alerts.find((a) => a.fragrance_id === fragranceId);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const { data } = await api.get<FragranceDetail>(`/catalog/fragrances/${fragranceId}`);
      setFragrance(data);
      navigation.setOptions({ title: data.name });
      // Secondary data: load in parallel, failures just hide the section.
      api.get<FragranceMatch[]>(`/fragrances/${fragranceId}/similar`, { params: { limit: 8 } })
        .then((r) => setSimilar(r.data)).catch(() => setSimilar([]));
      api.get<DupeItem[]>(`/fragrances/${fragranceId}/dupes`, { params: { limit: 5 } })
        .then((r) => setDupes(r.data)).catch(() => setDupes([]));
      api.get<PriceHistoryOut>(`/fragrances/${fragranceId}/price-history`)
        .then((r) => setHistory(r.data)).catch(() => setHistory(null));
      api.get<AlertOut[]>('/alerts').then((r) => setAlerts(r.data)).catch(() => setAlerts([]));
    } catch (err) {
      setLoadError(errorMessage(err, 'Could not load this fragrance'));
    } finally {
      setLoading(false);
    }
  }, [fragranceId, navigation]);

  useEffect(() => { loadAll(); }, [loadAll]);

  if (loading) {
    return (
      <View style={styles.container}>
        <View style={{ padding: spacing.base, gap: spacing.md }}>
          <Skeleton style={{ height: 140, borderRadius: radius.base }} />
          <Skeleton style={{ height: 90, borderRadius: radius.base }} />
          <Skeleton style={{ height: 160, borderRadius: radius.base }} />
        </View>
      </View>
    );
  }
  if (!fragrance) {
    return (
      <View style={[styles.container, { justifyContent: 'center' }]}>
        <EmptyState icon="cloud-offline-outline" title="Couldn't open this fragrance" body={loadError ?? undefined}
                    action={{ label: 'Try again', onPress: loadAll }} />
      </View>
    );
  }

  const minUsd = fragrance.prices.length ? Math.min(...fragrance.prices.map((p) => p.price_usd)) : null;
  const seasons = (['spring', 'summer', 'fall', 'winter'] as const)
    .filter((s) => fragrance[`season_${s}`]).map((s) => s[0].toUpperCase() + s.slice(1));
  const display = {
    fragrance_name: fragrance.name, brand_name: fragrance.brand.name, concentration: fragrance.concentration,
    gender: fragrance.gender, image_url: fragrance.image_url, families: fragrance.families.map((f) => f.name),
  };

  const quickAdd = async (status: 'own' | 'wishlist') => {
    if (status === 'own') {
      navigation.navigate('AddFragrance', { fragrance: { id: fragrance.id, ...display, sizes_ml: fragrance.prices.map((p) => p.size_ml) } });
      return;
    }
    setBusy(true);
    try {
      const res = await add({ fragrance_id: fragrance.id, status: 'wishlist', currency }, display);
      toast(res === 'exists' ? 'Already on your wishlist' : res === 'queued' ? 'Saved offline — will sync' : 'Added to wishlist', 'success');
    } catch (err) {
      toast(errorMessage(err), 'error');
    } finally {
      setBusy(false);
    }
  };

  const saveAlert = async () => {
    const value = parseFloat(target.replace(',', '.'));
    if (!value || value <= 0) {
      toast('Enter the price you want to pay', 'error');
      return;
    }
    setBusy(true);
    try {
      const body = { target_price: value, size_ml: alertSize, currency };
      const { data } = alert
        ? await api.patch<AlertOut>(`/alerts/${alert.id}`, { ...body, active: true })
        : await api.post<AlertOut>('/alerts', { fragrance_id: fragrance.id, ...body });
      setAlerts([data, ...alerts.filter((a) => a.id !== data.id)]);
      setAlertOpen(false);
      toast(`We'll notify you below ${money(value, currency)}`, 'success');
    } catch (err) {
      toast(errorMessage(err), 'error');
    } finally {
      setBusy(false);
    }
  };

  const removeAlert = async () => {
    if (!alert) return;
    try {
      await api.delete(`/alerts/${alert.id}`);
      setAlerts(alerts.filter((a) => a.id !== alert.id));
      toast('Alert removed', 'info');
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  };

  const wearToday = async (b: LocalBottle) => {
    try {
      await logWear(b);
      toast(`Logged ${b.fragrance_name} for today`, 'success');
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  };

  const costPerWear = (b: LocalBottle): string | null => {
    if (b.purchase_price == null) return null;
    if (b.wear_count >= MIN_REAL_WEARS) return money(b.purchase_price / b.wear_count, b.currency);
    if (!b.size_ml) return null;
    return `~${money(b.purchase_price / (b.size_ml / EST_ML_PER_WEAR), b.currency)} est.`;
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      {/* Header */}
      <View style={styles.header}>
        <BottleImage uri={fragrance.image_url} brand={fragrance.brand.name} size={120} rounded={20} />
        <Text style={styles.name}>{fragrance.name}</Text>
        <Text style={styles.brand}>{fragrance.brand.name} · {fragrance.concentration} · {fragrance.gender}</Text>
        {minUsd != null && <Text style={styles.price}>from {money(fromUsd(minUsd, currency, rates), currency)}</Text>}
        {fragrance.discontinued && <Text style={styles.discontinued}>Discontinued</Text>}
      </View>

      {/* Your bottles */}
      {mine.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Your bottle{mine.length > 1 ? 's' : ''}</Text>
          {mine.map((b) => (
            <View key={b.local_id} style={styles.bottle}>
              <View style={styles.bottleTop}>
                {b.status === 'own' ? <BottleGauge remainingPct={b.remaining_pct} size={34} /> : null}
                <View style={{ flex: 1 }}>
                  <Text style={styles.bottleTitle}>
                    {STATUS_LABEL[b.status]} · {BOTTLE_LABEL[b.bottle_type]}{b.size_ml ? ` ${b.size_ml} ml` : ''}
                  </Text>
                  <Text style={styles.bottleSub}>
                    {b.status === 'own' ? `${b.remaining_pct}% left · ` : ''}
                    {b.wear_count ? `worn ${b.wear_count}× · last ${relativeDays(b.last_worn_on)}` : 'not worn yet'}
                    {costPerWear(b) ? ` · ${costPerWear(b)}/wear` : ''}
                  </Text>
                  <View style={{ marginTop: 4 }}><StarRating value={b.rating} size={13} /></View>
                </View>
                <Pressable onPress={() => setEditing(b)} style={styles.editBtn} accessibilityRole="button"
                           accessibilityLabel="Edit this bottle">
                  <Ionicons name="create-outline" size={18} color={colors.gold} />
                </Pressable>
              </View>
              {b.status === 'own' && (
                <Button title="Wearing this today" variant="secondary" onPress={() => wearToday(b)} style={{ marginTop: spacing.md }} />
              )}
            </View>
          ))}
        </View>
      )}

      {/* Actions */}
      <View style={styles.actions}>
        {owned.length === 0 && (
          <Button title={mine.length ? 'Add a bottle I own' : 'Add to collection'} onPress={() => quickAdd('own')} style={{ flex: 1 }} />
        )}
        {owned.length > 0 && <Button title="Add another size" variant="secondary" onPress={() => quickAdd('own')} style={{ flex: 1 }} />}
        {!mine.some((b) => b.status === 'wishlist') && owned.length === 0 && (
          <Button title="Wishlist" variant="secondary" loading={busy} onPress={() => quickAdd('wishlist')} />
        )}
      </View>

      {/* Price alert */}
      <View style={styles.alertCard}>
        <View style={styles.alertHead}>
          <Ionicons name="notifications-outline" size={18} color={colors.gold} />
          <Text style={styles.alertTitle}>
            {alert ? `Alert below ${money(alert.target_price, alert.currency)}${alert.size_ml ? ` · ${alert.size_ml} ml` : ''}` : 'Price alert'}
          </Text>
          {alert && (
            <Pressable onPress={removeAlert} hitSlop={8} accessibilityRole="button" accessibilityLabel="Remove price alert">
              <Ionicons name="trash-outline" size={16} color={colors.textMuted} />
            </Pressable>
          )}
        </View>
        <Text style={styles.alertBody}>
          {alert
            ? alert.best_price != null
              ? `Best recent price: ${money(alert.best_price, alert.currency)}.`
              : 'No recent prices yet — we check every new price that gets logged.'
            : 'Get a push notification when a retailer price drops below your target.'}
        </Text>
        {alertOpen ? (
          <View style={{ gap: spacing.sm, marginTop: spacing.sm }}>
            <View style={styles.alertRow}>
              <TextInput style={styles.input} value={target} onChangeText={setTarget} keyboardType="decimal-pad"
                         placeholder={`Notify me below (${currency})`} placeholderTextColor={colors.textDark}
                         accessibilityLabel="Target price" />
              <Button title="Save" onPress={saveAlert} loading={busy} style={{ minWidth: 90 }} />
            </View>
            {fragrance.prices.length > 0 && (
              <View style={styles.sizeRow}>
                <Chip small label="Any size" active={alertSize === null} onPress={() => setAlertSize(null)} />
                {fragrance.prices.map((p) => (
                  <Chip key={p.size_ml} small label={`${p.size_ml} ml`} active={alertSize === p.size_ml}
                        onPress={() => setAlertSize(p.size_ml)} />
                ))}
              </View>
            )}
          </View>
        ) : (
          <Pressable onPress={() => { setTarget(alert ? String(alert.target_price) : ''); setAlertSize(alert?.size_ml ?? null); setAlertOpen(true); }}
                     style={styles.alertLink} accessibilityRole="button">
            <Text style={styles.alertLinkText}>{alert ? 'Change target' : 'Notify me below…'}</Text>
          </Pressable>
        )}
      </View>

      {/* Pyramid + facts */}
      <NotePyramid notes={fragrance.notes.map((n) => ({ name: n.name, position: n.position }))} />
      <View style={styles.facts}>
        <Fact label="SEASONS" value={seasons.length ? seasons.join(', ') : 'All year'} />
        <Fact label="OCCASIONS" value={fragrance.occasions.map((o) => o.name).join(', ') || 'Versatile'} />
        <Fact label="SILLAGE" value={fragrance.sillage ?? '—'} />
        <Fact label="LONGEVITY" value={fragrance.longevity_hours ? `${fragrance.longevity_hours} h` : '—'} />
        {fragrance.families.length > 0 && <Fact label="FAMILY" value={fragrance.families.map((f) => f.name).join(', ')} />}
        {fragrance.accords.length > 0 && <Fact label="ACCORDS" value={fragrance.accords.map((a) => a.name).slice(0, 4).join(', ')} />}
      </View>
      {fragrance.description ? <Text style={styles.description}>{fragrance.description}</Text> : null}

      {/* Prices */}
      {history && <PriceHistory series={history.series} currency={currency} rate={rate} />}

      {/* Similar */}
      {similar.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Similar fragrances</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            {similar.map((s) => (
              <SimilarCard key={s.fragrance_id} name={s.name} brand={s.brand_name} similarityPct={s.similarity_pct}
                           onPress={() => navigation.push('FragranceDetail', { fragranceId: s.fragrance_id })} />
            ))}
          </ScrollView>
        </View>
      )}

      {/* Dupes */}
      {dupes.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Cheaper alternatives</Text>
          <Text style={styles.caption}>Compared per ml, so a travel size can't fake a bargain.</Text>
          {dupes.map((d) => (
            <Pressable key={d.fragrance_id} style={styles.dupe}
                       onPress={() => navigation.push('FragranceDetail', { fragranceId: d.fragrance_id })}
                       accessibilityRole="button" accessibilityLabel={`${d.name}, ${Math.round(d.similarity_pct)}% similar, ${d.savings_pct}% cheaper per ml`}>
              <View style={{ flex: 1 }}>
                <Text style={styles.dupeName} numberOfLines={1}>{d.name}</Text>
                <Text style={styles.dupeBrand}>{d.brand_name} · {Math.round(d.similarity_pct)}% similar</Text>
                <View style={styles.simBg}><View style={[styles.simFill, { width: `${d.similarity_pct}%` }]} /></View>
              </View>
              <View style={{ alignItems: 'flex-end', marginLeft: spacing.md }}>
                <Text style={styles.dupePrice}>{money(fromUsd(d.price_usd, currency, rates), currency)}</Text>
                <Text style={styles.dupeSize}>{d.size_ml} ml</Text>
                <Text style={styles.dupeSave}>−{d.savings_pct}% / ml</Text>
              </View>
            </Pressable>
          ))}
        </View>
      )}

      <View style={{ height: spacing['3xl'] }} />
      {busy && <ActivityIndicator color={colors.gold} />}
      <BottleSheet bottle={editing} onClose={() => setEditing(null)} />
    </ScrollView>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.fact} accessible accessibilityLabel={`${label.toLowerCase()}: ${value}`}>
      <Text style={styles.factLabel}>{label}</Text>
      <Text style={styles.factValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingHorizontal: spacing.base },
  header: { alignItems: 'center', paddingVertical: spacing.xl, gap: 4 },
  name: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 24, color: colors.text, textAlign: 'center', marginTop: spacing.md },
  brand: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: colors.textMuted },
  price: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 18, color: colors.gold, marginTop: spacing.sm },
  discontinued: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: colors.warning, marginTop: 4 },
  section: { marginBottom: spacing.lg },
  sectionTitle: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 17, color: colors.text, marginBottom: spacing.sm },
  caption: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: colors.textMuted, marginBottom: spacing.sm },
  bottle: { backgroundColor: colors.card, borderRadius: radius.base, borderWidth: 1, borderColor: colors.goldDim, padding: spacing.base, marginBottom: spacing.sm },
  bottleTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  bottleTitle: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: colors.text },
  bottleSub: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: colors.textMuted, marginTop: 2 },
  editBtn: { width: 40, height: 40, borderRadius: 20, borderWidth: 1, borderColor: colors.goldDim, justifyContent: 'center', alignItems: 'center' },
  actions: { flexDirection: 'row', gap: spacing.md, marginBottom: spacing.lg },
  alertCard: { backgroundColor: colors.card, borderRadius: radius.base, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.base, marginBottom: spacing.lg },
  alertHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  alertTitle: { flex: 1, fontFamily: 'DMSans_700Bold', fontSize: 14, color: colors.text },
  alertBody: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: colors.textMuted, marginTop: 6, lineHeight: 18 },
  alertRow: { flexDirection: 'row', gap: spacing.sm, alignItems: 'center' },
  alertLink: { marginTop: spacing.sm, alignSelf: 'flex-start', paddingVertical: 4 },
  alertLinkText: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: colors.gold },
  sizeRow: { flexDirection: 'row', gap: spacing.sm, flexWrap: 'wrap' },
  input: { flex: 1, backgroundColor: colors.background, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, height: 44, paddingHorizontal: spacing.md, color: colors.text, fontFamily: 'DMSans_400Regular', fontSize: 14 },
  facts: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginBottom: spacing.base },
  fact: { flexGrow: 1, minWidth: '45%', backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.md, gap: 4 },
  factLabel: { fontFamily: 'DMSans_500Medium', fontSize: 11, color: colors.textDark, letterSpacing: 1 },
  factValue: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: colors.textSecondary },
  description: { fontFamily: 'DMSans_400Regular', fontSize: 13, lineHeight: 20, color: colors.textSecondary, marginBottom: spacing.base },
  dupe: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.md, marginBottom: spacing.sm },
  dupeName: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: colors.text },
  dupeBrand: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: colors.textMuted, marginTop: 2 },
  simBg: { height: 4, backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 2, marginTop: 6 },
  simFill: { height: 4, backgroundColor: colors.gold, borderRadius: 2 },
  dupePrice: { fontFamily: 'DMSans_700Bold', fontSize: 15, color: colors.text },
  dupeSize: { fontFamily: 'DMSans_400Regular', fontSize: 11, color: colors.textMuted },
  dupeSave: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: colors.success, marginTop: 2 },
});
