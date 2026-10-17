/**
 * Discover — AI search and personal recommendations.
 *
 * Results appear as soon as the vector search returns (well under a second);
 * the advisor's explanation is fetched afterwards and fades in when ready.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect, useNavigation, useRoute } from '@react-navigation/native';
import type { AIExplainOut, AISearchOut, AISearchResult, FragranceListItem, Page, RecommendationItem } from '@api-types';
import { colors } from '../theme/colors';
import { radius, spacing } from '../theme/spacing';
import { api, errorMessage, isNetworkError } from '../lib/api';
import { fromUsd, money } from '../lib/format';
import { useAuthStore, useCurrency } from '../stores/auth';
import { Banner, BottleImage, EmptyState, MatchRing, Skeleton, SkeletonRows } from '../components';

const QUICK_PROMPTS = [
  'Something like Aventus but cheaper',
  'Fresh office scent for summer',
  'Warm vanilla for winter evenings',
  'Clean and light, nothing too sweet',
  'Woody and smoky date night',
  'Citrus under 80',
];

interface CardItem {
  fragrance_id: number;
  name: string;
  brand_name: string;
  image_url: string | null;
  similarity_pct: number | null;
  min_price_usd: number | null;
  families: string[];
  detail?: string;
}

function ResultCard({ item, onPress }: { item: CardItem; onPress: () => void }) {
  const currency = useCurrency();
  const rates = useAuthStore((s) => s.meta.currencies);
  return (
    <Pressable style={styles.card} onPress={onPress} accessibilityRole="button"
               accessibilityLabel={`${item.name} by ${item.brand_name}${item.similarity_pct != null ? `, ${Math.round(item.similarity_pct)}% match` : ''}`}>
      {item.similarity_pct != null ? <MatchRing pct={item.similarity_pct} /> : <BottleImage uri={item.image_url} brand={item.brand_name} size={42} />}
      <View style={{ flex: 1 }}>
        <Text style={styles.cardName} numberOfLines={1}>{item.name}</Text>
        <Text style={styles.cardSub} numberOfLines={1}>
          {item.brand_name}{item.families[0] ? ` · ${item.families[0]}` : ''}
        </Text>
        {item.detail ? <Text style={styles.cardDetail} numberOfLines={2}>{item.detail}</Text> : null}
      </View>
      {item.min_price_usd != null && (
        <Text style={styles.cardPrice}>{money(fromUsd(item.min_price_usd, currency, rates), currency, 0)}</Text>
      )}
      <Ionicons name="chevron-forward" size={16} color={colors.textDark} />
    </Pressable>
  );
}

function BlindBuy({ item }: { item: RecommendationItem }) {
  const pct = item.similarity_pct;
  const [level, tint] = pct >= 85 ? ['Low', colors.success] : pct >= 65 ? ['Medium', colors.gold] : ['High', colors.error];
  const shared = item.shared_notes.length;
  return (
    <View style={styles.blind}>
      <View style={styles.blindHead}>
        <Ionicons name="shield-checkmark" size={18} color={tint} />
        <Text style={styles.blindLabel}>BLIND BUY CHECK</Text>
      </View>
      <View style={styles.blindBody}>
        <MatchRing pct={pct} size={56} />
        <View style={{ flex: 1, marginLeft: spacing.md }}>
          <Text style={styles.cardName} numberOfLines={1}>{item.name}</Text>
          <Text style={[styles.blindRisk, { color: tint }]}>{level} risk — {Math.round(pct)}% match with your taste</Text>
          <Text style={styles.cardSub}>
            {shared ? `Shares ${shared} note${shared > 1 ? 's' : ''} with bottles you rated 4★+ (${item.shared_notes.slice(0, 3).join(', ')})` : item.reason}
          </Text>
        </View>
      </View>
    </View>
  );
}

export function DiscoverScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const [query, setQuery] = useState('');
  const [active, setActive] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<CardItem[] | null>(null);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [recs, setRecs] = useState<RecommendationItem[] | null>(null);

  const loadRecs = useCallback(async () => {
    try {
      const { data } = await api.get<RecommendationItem[]>('/ai/recommend', { params: { limit: 10 } });
      setRecs(data);
    } catch {
      setRecs([]);
    }
  }, []);
  useFocusEffect(useCallback(() => { loadRecs(); }, [loadRecs]));

  const search = useCallback(async (raw?: string) => {
    const q = (raw ?? query).trim();
    if (!q) return;
    setActive(q);
    setSearching(true);
    setNotice(null);
    setResults(null);
    setExplanation(null);
    try {
      const { data } = await api.post<AISearchOut>('/ai/search', { query: q, limit: 10, explain: false });
      const cards = data.results.map((r: AISearchResult) => ({
        ...r,
        detail: [r.top_notes.slice(0, 2), r.base_notes.slice(0, 2)].flat().join(', ') || undefined,
      }));
      setResults(cards);
      if (cards.length) {
        setExplaining(true);
        api.post<AIExplainOut>('/ai/explain', { query: q, fragrance_ids: cards.slice(0, 5).map((c) => c.fragrance_id) }, { timeout: 60000 })
          .then((r) => setExplanation(r.data.explanation))
          .catch(() => setExplanation(null))
          .finally(() => setExplaining(false));
      }
    } catch (err) {
      if (isNetworkError(err)) {
        setNotice("You're offline — AI search needs a connection.");
        setResults([]);
      } else {
        // AI unavailable: fall back to a plain catalog search so the user still gets something.
        try {
          const { data } = await api.get<Page<FragranceListItem>>('/catalog/fragrances', { params: { search: q, size: 10 } });
          setResults(data.items.map((f) => ({
            fragrance_id: f.id, name: f.name, brand_name: f.brand_name, image_url: f.image_url,
            similarity_pct: null, min_price_usd: f.min_price_usd, families: f.families,
          })));
          setNotice('AI search is unavailable right now — showing name matches instead.');
        } catch (inner) {
          setNotice(errorMessage(inner));
          setResults([]);
        }
      }
    } finally {
      setSearching(false);
    }
  }, [query]);

  useEffect(() => {
    const initial = route.params?.initialQuery as string | undefined;
    if (initial) {
      setQuery(initial);
      search(initial);
      navigation.setParams({ initialQuery: undefined });
    }
  }, [route.params?.initialQuery]); // eslint-disable-line react-hooks/exhaustive-deps

  const clear = () => {
    setQuery('');
    setActive(null);
    setResults(null);
    setExplanation(null);
    setNotice(null);
  };

  const open = (id: number) => navigation.navigate('FragranceDetail', { fragranceId: id });

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}><Text style={styles.title}>Discover</Text></View>
      <View style={styles.searchWrap}>
        <View style={styles.searchBar}>
          <Ionicons name="sparkles" size={16} color={colors.gold} />
          <TextInput style={styles.input} value={query} onChangeText={setQuery} returnKeyType="search"
                     onSubmitEditing={() => search()} placeholder="Try: warm vanilla for winter evenings"
                     placeholderTextColor={colors.textMuted} accessibilityLabel="Describe what you're looking for" />
          {query.length > 0 && (
            <Pressable onPress={clear} accessibilityRole="button" accessibilityLabel="Clear search">
              <Ionicons name="close-circle" size={18} color={colors.textMuted} />
            </Pressable>
          )}
          <Pressable style={[styles.go, !query.trim() && { opacity: 0.4 }]} onPress={() => search()}
                     disabled={!query.trim() || searching} accessibilityRole="button" accessibilityLabel="Search">
            <Ionicons name="arrow-forward" size={16} color={colors.background} />
          </Pressable>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
        {notice && <Banner tone="info" text={notice} />}

        {searching && <SkeletonRows count={5} height={64} />}

        {!searching && results && (
          <View style={styles.section}>
            {(explaining || explanation) && (
              <View style={styles.advice}>
                <Ionicons name="sparkles" size={14} color={colors.gold} />
                {explanation ? (
                  <Text style={styles.adviceText}>{explanation}</Text>
                ) : (
                  <View style={{ flex: 1, gap: 6 }}>
                    <Skeleton style={{ height: 10, width: '90%' }} />
                    <Skeleton style={{ height: 10, width: '70%' }} />
                  </View>
                )}
              </View>
            )}
            {results.length === 0 && !notice ? (
              <EmptyState icon="search-outline" title="No matches" body={`Nothing fits “${active}”. Try fewer constraints.`} />
            ) : results.map((r) => <ResultCard key={r.fragrance_id} item={r} onPress={() => open(r.fragrance_id)} />)}
          </View>
        )}

        {!searching && !results && (
          <>
            <Text style={styles.label}>TRY ASKING</Text>
            <View style={styles.prompts}>
              {QUICK_PROMPTS.map((p) => (
                <Pressable key={p} style={styles.prompt} onPress={() => { setQuery(p); search(p); }} accessibilityRole="button">
                  <Text style={styles.promptText}>{p}</Text>
                </Pressable>
              ))}
            </View>

            {recs === null ? (
              <SkeletonRows count={3} height={64} />
            ) : recs.length > 0 ? (
              <>
                <BlindBuy item={recs[0]} />
                <Text style={styles.label}>FOR YOU</Text>
                {recs.map((r) => (
                  <ResultCard key={r.fragrance_id} item={{ ...r, detail: r.reason }} onPress={() => open(r.fragrance_id)} />
                ))}
              </>
            ) : (
              <EmptyState icon="heart-outline" title="Recommendations unlock with ratings"
                          body="Rate a few bottles 4★ or more (or mark favourites) and we'll find more like them." />
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
  header: { paddingHorizontal: spacing.base, paddingTop: spacing.base, paddingBottom: spacing.sm },
  title: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 24, color: colors.text },
  searchWrap: { paddingHorizontal: spacing.base, paddingBottom: spacing.md },
  searchBar: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.goldDim, height: 50, paddingLeft: spacing.md, paddingRight: 4, gap: spacing.sm },
  input: { flex: 1, color: colors.text, fontFamily: 'DMSans_400Regular', fontSize: 14 },
  go: { width: 42, height: 42, borderRadius: radius.sm, backgroundColor: colors.gold, justifyContent: 'center', alignItems: 'center' },
  scroll: { paddingHorizontal: spacing.base },
  section: { marginBottom: spacing.lg },
  label: { fontFamily: 'DMSans_500Medium', fontSize: 11, color: colors.textMuted, letterSpacing: 1.5, marginTop: spacing.lg, marginBottom: spacing.md },
  prompts: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  prompt: { backgroundColor: colors.card, borderRadius: 20, borderWidth: 1, borderColor: colors.cardBorder, paddingHorizontal: 14, paddingVertical: 9 },
  promptText: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: colors.textSecondary },
  advice: { flexDirection: 'row', gap: spacing.sm, backgroundColor: colors.card, borderRadius: radius.base, borderWidth: 1, borderColor: colors.goldDim, padding: spacing.base, marginBottom: spacing.md },
  adviceText: { flex: 1, fontFamily: 'DMSans_400Regular', fontSize: 13, lineHeight: 20, color: colors.textSecondary },
  card: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.md, marginBottom: spacing.sm },
  cardName: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: colors.text },
  cardSub: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: colors.textMuted, marginTop: 2 },
  cardDetail: { fontFamily: 'DMSans_400Regular', fontSize: 11, color: colors.textDark, marginTop: 3 },
  cardPrice: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: colors.gold },
  blind: { backgroundColor: colors.card, borderRadius: radius.base, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.base, marginTop: spacing.lg },
  blindHead: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: spacing.md },
  blindLabel: { fontFamily: 'DMSans_500Medium', fontSize: 11, letterSpacing: 1.5, color: colors.textSecondary },
  blindBody: { flexDirection: 'row', alignItems: 'center' },
  blindRisk: { fontFamily: 'DMSans_500Medium', fontSize: 12, marginTop: 2 },
});
