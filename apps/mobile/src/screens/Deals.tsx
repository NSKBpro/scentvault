/**
 * Deals — notifications, your price alerts, price drops (per size) and dupes for your bottles.
 * The old "alert" switches only set local state; alerts are now real and per fragrance.
 */
import React, { useCallback, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import Svg, { Circle, Polyline } from 'react-native-svg';
import type { AlertOut, CollectionDupe, NotificationOut, NotificationPage, PriceDropOut } from '@api-types';
import { colors } from '../theme/colors';
import { radius, spacing } from '../theme/spacing';
import { api, errorMessage, isNetworkError } from '../lib/api';
import { fromUsd, money, relativeDays } from '../lib/format';
import { useAuthStore, useCurrency } from '../stores/auth';
import { useUIStore } from '../stores/ui';
import { Banner, BottleImage, EmptyState, SkeletonRows } from '../components';

const KIND_ICON: Record<NotificationOut['kind'], React.ComponentProps<typeof Ionicons>['name']> = {
  price_alert: 'pricetag', running_low: 'battery-dead-outline', neglected: 'time-outline', system: 'information-circle-outline',
};

function Sparkline({ data }: { data: number[] }) {
  if (data.length < 2) return null;
  const W = 72;
  const H = 24;
  const lo = Math.min(...data);
  const range = Math.max(...data) - lo || 1;
  const pts = data.map((p, i) => ({ x: 2 + (i / (data.length - 1)) * (W - 4), y: H - 2 - ((p - lo) / range) * (H - 4) }));
  const last = pts[pts.length - 1];
  return (
    <Svg width={W} height={H} accessibilityElementsHidden>
      <Polyline points={pts.map((p) => `${p.x},${p.y}`).join(' ')} fill="none" stroke={colors.gold} strokeWidth={1.5} />
      <Circle cx={last.x} cy={last.y} r={2.5} fill={colors.success} />
    </Svg>
  );
}

export function DealsScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const currency = useCurrency();
  const rates = useAuthStore((s) => s.meta.currencies);
  const toast = useUIStore((s) => s.showToast);
  const [inbox, setInbox] = useState<NotificationPage | null>(null);
  const [alerts, setAlerts] = useState<AlertOut[]>([]);
  const [drops, setDrops] = useState<PriceDropOut[]>([]);
  const [dupes, setDupes] = useState<CollectionDupe[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAllInbox, setShowAllInbox] = useState(false);

  const load = useCallback(async () => {
    try {
      const [n, a, d, du] = await Promise.all([
        api.get<NotificationPage>('/notifications', { params: { limit: 30 } }),
        api.get<AlertOut[]>('/alerts'),
        api.get<PriceDropOut[]>('/deals/price-drops', { params: { min_drop_pct: 5, limit: 20 } }),
        api.get<CollectionDupe[]>('/deals/dupes-for-collection', { params: { limit: 10 } }),
      ]);
      setInbox(n.data);
      setAlerts(a.data);
      setDrops(d.data);
      setDupes(du.data);
      setError(null);
    } catch (err) {
      setError(isNetworkError(err) ? "You're offline — deals need a connection." : errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const usd = (v: number | null) => money(fromUsd(v, currency, rates), currency);
  const open = (id: number) => navigation.navigate('FragranceDetail', { fragranceId: id });

  const readAll = async () => {
    try {
      await api.post('/notifications/read-all');
      setInbox((i) => (i ? { unread: 0, items: i.items.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })) } : i));
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  };

  const tapNotification = async (n: NotificationOut) => {
    if (!n.read_at) {
      api.post(`/notifications/${n.id}/read`).catch(() => undefined);
      setInbox((i) => (i ? { unread: Math.max(0, i.unread - 1), items: i.items.map((x) => (x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x)) } : i));
    }
    const fid = n.payload?.fragrance_id;
    if (typeof fid === 'number') open(fid);
  };

  const toggleAlert = async (a: AlertOut) => {
    try {
      const { data } = await api.patch<AlertOut>(`/alerts/${a.id}`, { active: !a.active });
      setAlerts((list) => list.map((x) => (x.id === a.id ? data : x)));
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  };

  const notifications = inbox?.items ?? [];
  const shown = showAllInbox ? notifications : notifications.slice(0, 4);

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}><Text style={styles.title}>Deals</Text></View>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}
                  refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.gold} />}>
        {error && <Banner tone={error.includes('offline') ? 'warning' : 'error'} text={error} onPress={load} />}
        {loading ? <SkeletonRows count={5} /> : (
          <>
            {/* Notifications */}
            {notifications.length > 0 && (
              <View style={styles.section}>
                <View style={styles.sectionHead}>
                  <Ionicons name="notifications" size={16} color={colors.gold} />
                  <Text style={styles.sectionTitle}>Notifications{inbox?.unread ? ` · ${inbox.unread} new` : ''}</Text>
                  {inbox?.unread ? (
                    <Pressable onPress={readAll} accessibilityRole="button"><Text style={styles.link}>Mark all read</Text></Pressable>
                  ) : null}
                </View>
                {shown.map((n) => (
                  <Pressable key={n.id} style={[styles.note, !n.read_at && styles.noteUnread]} onPress={() => tapNotification(n)}
                             accessibilityRole="button" accessibilityLabel={`${n.read_at ? '' : 'Unread. '}${n.title}. ${n.body}`}>
                    <Ionicons name={KIND_ICON[n.kind]} size={18} color={n.read_at ? colors.textDark : colors.gold} />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.noteTitle}>{n.title}</Text>
                      <Text style={styles.noteBody}>{n.body}</Text>
                      <Text style={styles.noteTime}>{relativeDays(n.created_at)}</Text>
                    </View>
                  </Pressable>
                ))}
                {notifications.length > 4 && (
                  <Pressable onPress={() => setShowAllInbox(!showAllInbox)} accessibilityRole="button">
                    <Text style={[styles.link, { textAlign: 'center', marginTop: spacing.xs }]}>
                      {showAllInbox ? 'Show less' : `Show all ${notifications.length}`}
                    </Text>
                  </Pressable>
                )}
              </View>
            )}

            {/* My alerts */}
            <View style={styles.section}>
              <View style={styles.sectionHead}>
                <Ionicons name="alarm-outline" size={16} color={colors.gold} />
                <Text style={styles.sectionTitle}>Price alerts</Text>
              </View>
              {alerts.length === 0 ? (
                <Text style={styles.muted}>
                  Open any fragrance and tap “Notify me below…” — we push you when a logged price drops under your target.
                </Text>
              ) : alerts.map((a) => {
                const hit = a.best_price != null && a.best_price <= a.target_price;
                return (
                  <Pressable key={a.id} style={styles.row} onPress={() => open(a.fragrance_id)} accessibilityRole="button">
                    <View style={{ flex: 1 }}>
                      <Text style={styles.rowName} numberOfLines={1}>{a.fragrance_name}</Text>
                      <Text style={styles.rowSub}>
                        {a.brand_name} · below {money(a.target_price, a.currency)}{a.size_ml ? ` · ${a.size_ml} ml` : ''}
                      </Text>
                      <Text style={[styles.rowSub, hit && { color: colors.success }]}>
                        {a.best_price != null ? `Best recent: ${money(a.best_price, a.currency)}` : 'No recent prices yet'}
                      </Text>
                    </View>
                    <Switch value={a.active} onValueChange={() => toggleAlert(a)}
                            trackColor={{ false: colors.textDark, true: colors.gold }} thumbColor={colors.text}
                            accessibilityLabel={`Alert for ${a.fragrance_name} ${a.active ? 'on' : 'off'}`} />
                  </Pressable>
                );
              })}
            </View>

            {/* Price drops */}
            {drops.length > 0 && (
              <View style={styles.section}>
                <View style={styles.sectionHead}>
                  <Ionicons name="trending-down" size={16} color={colors.success} />
                  <Text style={styles.sectionTitle}>Price drops</Text>
                </View>
                {drops.map((d) => (
                  <Pressable key={`${d.fragrance_id}-${d.size_ml}`} style={styles.row} onPress={() => open(d.fragrance_id)}
                             accessibilityRole="button" accessibilityLabel={`${d.fragrance_name} ${d.size_ml} ml, down ${d.drop_pct}%`}>
                    <BottleImage uri={d.image_url} brand={d.brand_name} size={40} rounded={10} />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.rowName} numberOfLines={1}>{d.fragrance_name}</Text>
                      <Text style={styles.rowSub} numberOfLines={1}>{d.brand_name} · {d.size_ml} ml · {d.retailer_name}</Text>
                    </View>
                    <Sparkline data={d.history} />
                    <View style={{ alignItems: 'flex-end' }}>
                      <Text style={styles.price}>{usd(d.current_price_usd)}</Text>
                      <Text style={styles.drop}>−{d.drop_pct}%</Text>
                    </View>
                  </Pressable>
                ))}
              </View>
            )}

            {/* Dupes */}
            {dupes.length > 0 && (
              <View style={styles.section}>
                <View style={styles.sectionHead}>
                  <Ionicons name="copy-outline" size={16} color={colors.gold} />
                  <Text style={styles.sectionTitle}>Cheaper alternatives</Text>
                </View>
                <Text style={styles.muted}>For bottles you own or want. Compared per ml.</Text>
                {dupes.map((x) => (
                  <View key={x.original_id} style={styles.dupe}>
                    <Text style={styles.dupeKicker}>INSTEAD OF</Text>
                    <Text style={styles.rowName}>{x.original_name} <Text style={styles.rowSub}>· {x.original_brand}</Text></Text>
                    <Pressable style={styles.dupeAlt} onPress={() => open(x.dupe.fragrance_id)} accessibilityRole="button">
                      <View style={{ flex: 1 }}>
                        <Text style={styles.rowName} numberOfLines={1}>{x.dupe.name}</Text>
                        <Text style={styles.rowSub}>{x.dupe.brand_name} · {Math.round(x.dupe.similarity_pct)}% similar</Text>
                      </View>
                      <View style={{ alignItems: 'flex-end' }}>
                        <Text style={styles.price}>{usd(x.dupe.price_usd)}</Text>
                        <Text style={styles.drop}>−{x.dupe.savings_pct}% / ml</Text>
                      </View>
                    </Pressable>
                  </View>
                ))}
              </View>
            )}

            {!error && drops.length === 0 && dupes.length === 0 && notifications.length === 0 && (
              <EmptyState icon="pricetag-outline" title="No deals yet"
                          body="Price drops appear as prices get logged. Wishlist something and set an alert to get notified." />
            )}
          </>
        )}
        <View style={{ height: spacing['3xl'] }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { paddingHorizontal: spacing.base, paddingTop: spacing.base, paddingBottom: spacing.md },
  title: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 24, color: colors.text },
  scroll: { paddingHorizontal: spacing.base },
  section: { marginBottom: spacing.xl },
  sectionHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.md },
  sectionTitle: { flex: 1, fontFamily: 'PlayfairDisplay_700Bold', fontSize: 17, color: colors.text },
  link: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: colors.gold },
  muted: { fontFamily: 'DMSans_400Regular', fontSize: 13, lineHeight: 19, color: colors.textMuted, marginBottom: spacing.sm },
  note: { flexDirection: 'row', gap: spacing.md, backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.md, marginBottom: spacing.sm },
  noteUnread: { borderColor: colors.goldDim },
  noteTitle: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: colors.text },
  noteBody: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: colors.textSecondary, marginTop: 2, lineHeight: 18 },
  noteTime: { fontFamily: 'DMSans_400Regular', fontSize: 11, color: colors.textDark, marginTop: 4 },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.md, marginBottom: spacing.sm },
  rowName: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: colors.text },
  rowSub: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: colors.textMuted, marginTop: 2 },
  price: { fontFamily: 'DMSans_700Bold', fontSize: 15, color: colors.text },
  drop: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: colors.success, marginTop: 2 },
  dupe: { backgroundColor: colors.card, borderRadius: radius.base, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.md, marginBottom: spacing.sm },
  dupeKicker: { fontFamily: 'DMSans_500Medium', fontSize: 10, letterSpacing: 1.2, color: colors.textDark, marginBottom: 2 },
  dupeAlt: { flexDirection: 'row', alignItems: 'center', marginTop: spacing.md, paddingTop: spacing.md, borderTopWidth: 1, borderTopColor: colors.cardBorder },
});
