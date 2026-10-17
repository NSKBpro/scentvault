/**
 * Add to collection: search the catalog → fill in the bottle → save (works offline too).
 * Opened with `route.params.fragrance` it skips straight to the details step.
 */
import { useEffect, useState } from 'react';
import {
  FlatList, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { BottleType, CollectionStatus, FragranceListItem, Page } from '@api-types';
import { colors } from '../theme/colors';
import { radius, spacing } from '../theme/spacing';
import { api, errorMessage } from '../lib/api';
import { BOTTLE_LABEL, todayISO } from '../lib/format';
import { useAuthStore, useCurrency } from '../stores/auth';
import { useCollectionStore } from '../stores/collection';
import { useUIStore } from '../stores/ui';
import { BottleImage, Button, Chip, EmptyState, SkeletonRows, StarRating } from '../components';

interface Picked {
  id: number;
  fragrance_name: string;
  brand_name: string;
  concentration: string;
  gender: string;
  image_url: string | null;
  families: string[];
  sizes_ml: number[];
}

const fromListItem = (f: FragranceListItem): Picked => ({
  id: f.id, fragrance_name: f.name, brand_name: f.brand_name, concentration: f.concentration, gender: f.gender,
  image_url: f.image_url, families: f.families, sizes_ml: f.sizes_ml,
});

function SearchStep({ onSelect }: { onSelect: (f: Picked) => void }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<FragranceListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      setError(null);
      return;
    }
    let cancelled = false;
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const { data } = await api.get<Page<FragranceListItem>>('/catalog/fragrances', {
          params: { search: q, size: 30, sort: 'name' },
        });
        if (!cancelled) { setResults(data.items); setError(null); }
      } catch (err) {
        if (!cancelled) setError(errorMessage(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 300);
    return () => { cancelled = true; clearTimeout(t); };
  }, [query]);

  return (
    <View style={styles.step}>
      <View style={styles.searchBar}>
        <Ionicons name="search" size={18} color={colors.textMuted} />
        <TextInput style={styles.searchInput} value={query} onChangeText={setQuery} autoFocus
                   placeholder="Search by fragrance or brand…" placeholderTextColor={colors.textMuted}
                   accessibilityLabel="Search fragrances" returnKeyType="search" />
        {query.length > 0 && (
          <Pressable onPress={() => setQuery('')} accessibilityRole="button" accessibilityLabel="Clear search">
            <Ionicons name="close-circle" size={18} color={colors.textMuted} />
          </Pressable>
        )}
      </View>
      {loading && results.length === 0 ? <SkeletonRows count={5} height={60} /> : null}
      {error ? <EmptyState icon="cloud-offline-outline" title="Search unavailable" body={error} /> : null}
      {!loading && !error && query.trim().length >= 2 && results.length === 0 && (
        <EmptyState icon="search-outline" title="No matches" body="Try the brand name, or fewer words. Missing a fragrance? Ask your admin to add it." />
      )}
      <FlatList
        data={results}
        keyExtractor={(f) => String(f.id)}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ paddingBottom: 40 }}
        renderItem={({ item }) => (
          <Pressable style={styles.result} onPress={() => onSelect(fromListItem(item))} accessibilityRole="button"
                     accessibilityLabel={`${item.name} by ${item.brand_name}, ${item.concentration}`}>
            <BottleImage uri={item.image_url} brand={item.brand_name} size={44} rounded={10} />
            <View style={{ flex: 1 }}>
              <Text style={styles.resultName} numberOfLines={1}>{item.name}</Text>
              <Text style={styles.resultSub} numberOfLines={1}>
                {item.brand_name} · {item.concentration}{item.release_year ? ` · ${item.release_year}` : ''}
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={colors.textDark} />
          </Pressable>
        )}
      />
    </View>
  );
}

function DetailsStep({ fragrance, onBack }: { fragrance: Picked; onBack?: () => void }) {
  const navigation = useNavigation<any>();
  const add = useCollectionStore((s) => s.add);
  const toast = useUIStore((s) => s.showToast);
  const defaultCurrency = useCurrency();
  const currencies = Object.keys(useAuthStore((s) => s.meta.currencies));

  const sizes = fragrance.sizes_ml.length ? fragrance.sizes_ml : [30, 50, 100];
  const [status, setStatus] = useState<CollectionStatus>('own');
  const [type, setType] = useState<BottleType>('full');
  const [size, setSize] = useState<string>(String(sizes[sizes.length - 1]));
  const [price, setPrice] = useState('');
  const [currency, setCurrency] = useState(defaultCurrency);
  const [date, setDate] = useState(todayISO());
  const [rating, setRating] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      const result = await add({
        fragrance_id: fragrance.id,
        status,
        bottle_type: type,
        size_ml: status === 'wishlist' || !size ? null : parseInt(size, 10),
        purchase_price: price ? parseFloat(price.replace(',', '.')) : null,
        currency,
        purchase_date: status === 'own' && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : null,
        rating,
      }, fragrance);
      if (result === 'exists') {
        toast('That bottle is already in your collection', 'info');
        return;
      }
      toast(result === 'queued' ? 'Saved on this phone — it will sync when you are online' : `${fragrance.fragrance_name} added`, 'success');
      navigation.goBack();
    } catch (err) {
      toast(errorMessage(err), 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.step} keyboardShouldPersistTaps="handled">
        {onBack && (
          <Pressable onPress={onBack} style={styles.back} accessibilityRole="button">
            <Ionicons name="chevron-back" size={18} color={colors.gold} />
            <Text style={styles.backText}>Choose another</Text>
          </Pressable>
        )}
        <View style={styles.picked}>
          <BottleImage uri={fragrance.image_url} brand={fragrance.brand_name} size={56} />
          <View style={{ flex: 1 }}>
            <Text style={styles.pickedName}>{fragrance.fragrance_name}</Text>
            <Text style={styles.pickedSub}>{fragrance.brand_name} · {fragrance.concentration}</Text>
          </View>
        </View>

        <Text style={styles.label}>Status</Text>
        <View style={styles.wrap}>
          {(['own', 'wishlist', 'tried'] as const).map((s) => (
            <Chip key={s} label={s === 'own' ? 'I own this' : s === 'wishlist' ? 'Wishlist' : 'Tried it'}
                  active={status === s} onPress={() => setStatus(s)} />
          ))}
        </View>

        {status !== 'wishlist' && (
          <>
            <Text style={styles.label}>Bottle</Text>
            <View style={styles.wrap}>
              {(['full', 'decant', 'sample', 'tester'] as const).map((t) => (
                <Chip key={t} label={BOTTLE_LABEL[t]} active={type === t} onPress={() => setType(t)} />
              ))}
            </View>
            <Text style={styles.label}>Size (ml)</Text>
            <View style={styles.wrap}>
              {(type === 'full' ? sizes : [2, 5, 10]).map((s) => (
                <Chip key={s} label={`${s} ml`} active={size === String(s)} onPress={() => setSize(String(s))} />
              ))}
              <TextInput style={[styles.input, styles.sizeInput]} value={size} onChangeText={setSize}
                         keyboardType="number-pad" placeholder="Other" placeholderTextColor={colors.textDark}
                         accessibilityLabel="Custom size in millilitres" />
            </View>
          </>
        )}

        {status === 'own' && (
          <>
            <Text style={styles.label}>Price paid</Text>
            <View style={styles.row}>
              <TextInput style={[styles.input, { flex: 1 }]} value={price} onChangeText={setPrice}
                         keyboardType="decimal-pad" placeholder="Optional" placeholderTextColor={colors.textDark}
                         accessibilityLabel="Price paid" />
              {currencies.map((c) => <Chip key={c} small label={c} active={currency === c} onPress={() => setCurrency(c)} />)}
            </View>
            <Text style={styles.label}>Purchase date</Text>
            <TextInput style={styles.input} value={date} onChangeText={setDate} placeholder="YYYY-MM-DD"
                       placeholderTextColor={colors.textDark} accessibilityLabel="Purchase date" />
          </>
        )}

        {status !== 'wishlist' && (
          <>
            <Text style={styles.label}>Your rating</Text>
            <StarRating value={rating} onChange={setRating} size={30} />
          </>
        )}

        <Button title={status === 'wishlist' ? 'Add to wishlist' : 'Add to collection'} onPress={save} loading={saving}
                style={{ marginTop: spacing['2xl'] }} />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

export function AddFragranceScreen() {
  const route = useRoute<any>();
  const preset: Picked | undefined = route.params?.fragrance
    ? { families: [], sizes_ml: [], ...route.params.fragrance }
    : undefined;
  const [selected, setSelected] = useState<Picked | null>(preset ?? null);
  return (
    <View style={styles.container}>
      {selected
        ? <DetailsStep fragrance={selected} onBack={preset ? undefined : () => setSelected(null)} />
        : <SearchStep onSelect={setSelected} />}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  step: { flexGrow: 1, paddingHorizontal: spacing.base, paddingTop: spacing.base, paddingBottom: spacing['2xl'] },
  searchBar: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, height: 46, paddingHorizontal: spacing.md, gap: spacing.sm, marginBottom: spacing.base },
  searchInput: { flex: 1, color: colors.text, fontFamily: 'DMSans_400Regular', fontSize: 15 },
  result: { flexDirection: 'row', alignItems: 'center', paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.cardBorder, gap: spacing.md },
  resultName: { fontFamily: 'DMSans_500Medium', fontSize: 15, color: colors.text },
  resultSub: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: colors.textMuted, marginTop: 2 },
  back: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: spacing.base },
  backText: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: colors.gold },
  picked: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, marginBottom: spacing.sm },
  pickedName: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 20, color: colors.text },
  pickedSub: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: colors.textMuted },
  label: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: colors.textSecondary, letterSpacing: 0.5, marginBottom: spacing.sm, marginTop: spacing.lg },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, alignItems: 'center' },
  row: { flexDirection: 'row', gap: spacing.sm, alignItems: 'center' },
  input: { backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, height: 44, paddingHorizontal: spacing.md, color: colors.text, fontFamily: 'DMSans_400Regular', fontSize: 14 },
  sizeInput: { width: 80, height: 34 },
});
