/**
 * "Your bottle" editor: every field of a collection item, plus finish / sell / remove.
 */
import React, { useEffect, useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import Slider from '@react-native-community/slider';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { BottleType, CollectionItemUpdate, CollectionStatus } from '@api-types';
import { colors } from '../theme/colors';
import { radius, spacing } from '../theme/spacing';
import { BOTTLE_LABEL, STATUS_LABEL, money } from '../lib/format';
import { errorMessage } from '../lib/api';
import type { LocalBottle } from '../lib/offlineDb';
import { useCollectionStore } from '../stores/collection';
import { useAuthStore } from '../stores/auth';
import { useUIStore } from '../stores/ui';
import { Button } from './Button';
import { Chip } from './Chip';
import { StarRating } from './StarRating';

const EDITABLE_STATUSES: CollectionStatus[] = ['own', 'wishlist', 'tried'];
const BOTTLE_TYPES: BottleType[] = ['full', 'decant', 'sample', 'tester'];
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

interface Props {
  bottle: LocalBottle | null;
  onClose: () => void;
}

export function BottleSheet({ bottle, onClose }: Props) {
  const insets = useSafeAreaInsets();
  const { update, finish, sell, remove } = useCollectionStore();
  const currencies = Object.keys(useAuthStore((s) => s.meta.currencies));
  const toast = useUIStore((s) => s.showToast);

  const [status, setStatus] = useState<CollectionStatus>('own');
  const [type, setType] = useState<BottleType>('full');
  const [size, setSize] = useState('');
  const [price, setPrice] = useState('');
  const [currency, setCurrency] = useState('EUR');
  const [date, setDate] = useState('');
  const [rating, setRating] = useState<number | null>(null);
  const [remaining, setRemaining] = useState(100);
  const [notes, setNotes] = useState('');
  const [favorite, setFavorite] = useState(false);
  const [selling, setSelling] = useState(false);
  const [soldPrice, setSoldPrice] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!bottle) return;
    setStatus(bottle.status);
    setType(bottle.bottle_type);
    setSize(bottle.size_ml ? String(bottle.size_ml) : '');
    setPrice(bottle.purchase_price != null ? String(bottle.purchase_price) : '');
    setCurrency(bottle.currency);
    setDate(bottle.purchase_date ?? '');
    setRating(bottle.rating);
    setRemaining(bottle.remaining_pct);
    setNotes(bottle.notes ?? '');
    setFavorite(bottle.is_favorite);
    setSelling(false);
    setSoldPrice('');
  }, [bottle]);

  if (!bottle) return null;
  const archived = !EDITABLE_STATUSES.includes(bottle.status);

  const run = async (fn: () => Promise<void>, done: string) => {
    setBusy(true);
    try {
      await fn();
      toast(done, 'success');
      onClose();
    } catch (err) {
      toast(errorMessage(err), 'error');
    } finally {
      setBusy(false);
    }
  };

  const save = () => {
    if (date && !DATE_RE.test(date)) {
      toast('Purchase date must look like 2026-09-01', 'error');
      return;
    }
    const patch: CollectionItemUpdate = {
      bottle_type: type,
      size_ml: size ? parseInt(size, 10) : null,
      purchase_price: price ? parseFloat(price.replace(',', '.')) : null,
      currency,
      purchase_date: date || null,
      rating,
      remaining_pct: Math.round(remaining),
      notes: notes.trim() || null,
      is_favorite: favorite,
      ...(archived ? {} : { status }),
    };
    run(() => update(bottle, patch), 'Bottle updated');
  };

  const confirmRemove = () =>
    Alert.alert('Remove from collection?', `${bottle.fragrance_name} and its wear history link will be removed.`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Remove', style: 'destructive', onPress: () => run(() => remove(bottle), 'Removed') },
    ]);

  return (
    <Modal visible animationType="slide" transparent onRequestClose={onClose}>
      <KeyboardAvoidingView style={styles.overlay} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="Close" />
        <View style={[styles.sheet, { paddingBottom: insets.bottom + spacing.base }]}>
          <View style={styles.header}>
            <View style={{ flex: 1 }}>
              <Text style={styles.kicker}>YOUR BOTTLE</Text>
              <Text style={styles.title} numberOfLines={1}>{bottle.fragrance_name}</Text>
              <Text style={styles.sub}>{bottle.brand_name}{bottle.synced ? '' : ' · waiting to sync'}</Text>
            </View>
            <Pressable onPress={onClose} hitSlop={10} accessibilityRole="button" accessibilityLabel="Close editor">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>

          <ScrollView contentContainerStyle={{ paddingBottom: spacing.base }} keyboardShouldPersistTaps="handled">
            {archived ? (
              <Text style={styles.archived}>
                {STATUS_LABEL[bottle.status]}
                {bottle.sold_at ? ` on ${bottle.sold_at}` : ''}
                {bottle.sold_price != null ? ` for ${money(bottle.sold_price, bottle.currency)}` : ''}
              </Text>
            ) : (
              <>
                <Text style={styles.label}>Status</Text>
                <View style={styles.wrapRow}>
                  {EDITABLE_STATUSES.map((s) => (
                    <Chip key={s} label={STATUS_LABEL[s]} active={status === s} onPress={() => setStatus(s)} />
                  ))}
                </View>
              </>
            )}

            <Text style={styles.label}>Bottle</Text>
            <View style={styles.wrapRow}>
              {BOTTLE_TYPES.map((t) => <Chip key={t} label={BOTTLE_LABEL[t]} active={type === t} onPress={() => setType(t)} />)}
            </View>

            <View style={styles.twoCol}>
              <View style={{ flex: 1 }}>
                <Text style={styles.label}>Size (ml)</Text>
                <TextInput style={styles.input} value={size} onChangeText={setSize} keyboardType="number-pad"
                           placeholder="100" placeholderTextColor={colors.textDark} accessibilityLabel="Size in millilitres" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.label}>Purchase date</Text>
                <TextInput style={styles.input} value={date} onChangeText={setDate} placeholder="YYYY-MM-DD"
                           placeholderTextColor={colors.textDark} accessibilityLabel="Purchase date" />
              </View>
            </View>

            <Text style={styles.label}>Price paid</Text>
            <View style={styles.twoCol}>
              <TextInput style={[styles.input, { flex: 1 }]} value={price} onChangeText={setPrice}
                         keyboardType="decimal-pad" placeholder="Optional" placeholderTextColor={colors.textDark}
                         accessibilityLabel="Price paid" />
              <View style={[styles.wrapRow, { flex: 1.4 }]}>
                {currencies.map((c) => <Chip key={c} small label={c} active={currency === c} onPress={() => setCurrency(c)} />)}
              </View>
            </View>

            <Text style={styles.label}>Your rating</Text>
            <StarRating value={rating} onChange={setRating} size={28} />
            <Text style={styles.hint}>Tap a star; tap it again (or long-press) for a half star.</Text>

            {bottle.status === 'own' && (
              <>
                <Text style={styles.label}>Remaining · {Math.round(remaining)}%</Text>
                <Slider minimumValue={0} maximumValue={100} step={5} value={remaining} onValueChange={setRemaining}
                        minimumTrackTintColor={colors.gold} maximumTrackTintColor={colors.textDark}
                        thumbTintColor={colors.gold} accessibilityLabel="Remaining percentage" />
              </>
            )}

            <Text style={styles.label}>Notes</Text>
            <TextInput style={[styles.input, styles.notes]} value={notes} onChangeText={setNotes} multiline
                       placeholder="Where you bought it, batch code, how it wears on you…"
                       placeholderTextColor={colors.textDark} accessibilityLabel="Notes" />

            <View style={styles.switchRow}>
              <Text style={styles.switchLabel}>Favourite</Text>
              <Switch value={favorite} onValueChange={setFavorite} trackColor={{ false: colors.textDark, true: colors.gold }}
                      thumbColor={colors.text} accessibilityLabel="Favourite" />
            </View>

            <Button title="Save changes" onPress={save} loading={busy} style={{ marginTop: spacing.base }} />

            {!archived && bottle.status === 'own' && (
              <View style={styles.actions}>
                <Button title="Finished it" variant="secondary" style={{ flex: 1 }}
                        onPress={() => run(() => finish(bottle), 'Marked as finished')} />
                <Button title={selling ? 'Cancel' : 'Sold / gifted'} variant="secondary" style={{ flex: 1 }}
                        onPress={() => setSelling(!selling)} />
              </View>
            )}
            {selling && (
              <View style={styles.sellBox}>
                <TextInput style={[styles.input, { flex: 1 }]} value={soldPrice} onChangeText={setSoldPrice}
                           keyboardType="decimal-pad" placeholder={`Sold for (${bottle.currency})`}
                           placeholderTextColor={colors.textDark} accessibilityLabel="Sold price" />
                <Button title="Sold" style={{ paddingHorizontal: spacing.base }} onPress={() => run(
                  () => sell(bottle, { sold_price: soldPrice ? parseFloat(soldPrice.replace(',', '.')) : null }), 'Marked as sold')} />
                <Button title="Gift" variant="secondary" style={{ paddingHorizontal: spacing.base }}
                        onPress={() => run(() => sell(bottle, { gifted: true }), 'Marked as gifted')} />
              </View>
            )}
            <Pressable onPress={confirmRemove} style={styles.remove} accessibilityRole="button">
              <Ionicons name="trash-outline" size={16} color={colors.error} />
              <Text style={styles.removeText}>Remove from collection</Text>
            </Pressable>
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: colors.overlay, justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: colors.card, borderTopLeftRadius: radius.xl, borderTopRightRadius: radius.xl,
    paddingHorizontal: spacing.lg, paddingTop: spacing.lg, maxHeight: '92%',
    borderTopWidth: 1, borderColor: colors.cardBorder,
  },
  header: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: spacing.sm },
  kicker: { fontFamily: 'DMSans_500Medium', fontSize: 11, letterSpacing: 1.5, color: colors.gold },
  title: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 22, color: colors.text, marginTop: 2 },
  sub: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: colors.textMuted },
  archived: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: colors.textSecondary, marginTop: spacing.base },
  label: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: colors.textSecondary, marginTop: spacing.base, marginBottom: spacing.sm },
  hint: { fontFamily: 'DMSans_400Regular', fontSize: 11, color: colors.textDark, marginTop: 4 },
  wrapRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  twoCol: { flexDirection: 'row', gap: spacing.md, alignItems: 'flex-start' },
  input: {
    backgroundColor: colors.background, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder,
    height: 44, paddingHorizontal: spacing.md, color: colors.text, fontFamily: 'DMSans_400Regular', fontSize: 14,
  },
  notes: { height: 80, paddingTop: spacing.sm, textAlignVertical: 'top' },
  switchRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: spacing.base },
  switchLabel: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: colors.text },
  actions: { flexDirection: 'row', gap: spacing.md, marginTop: spacing.md },
  sellBox: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md, alignItems: 'center' },
  remove: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: spacing.lg, padding: spacing.sm },
  removeText: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: colors.error },
});
