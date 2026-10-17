/**
 * Price history per bottle size (sizes are never mixed): sparkline + latest / low / high / reference.
 * Data: public GET /fragrances/{id}/price-history.
 */
import React, { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Polyline } from 'react-native-svg';
import type { PriceSeries } from '@api-types';
import { colors } from '../theme/colors';
import { radius, spacing } from '../theme/spacing';
import { money } from '../lib/format';
import { Chip } from './Chip';

interface Props {
  series: PriceSeries[];
  currency: string;
  rate: number; // USD → display currency
}

export function PriceHistory({ series, currency, rate }: Props) {
  const withData = series.filter((s) => s.points.length > 0 || s.msrp_usd != null);
  const [size, setSize] = useState<number | null>(null);
  if (!withData.length) return null;
  const current = withData.find((s) => s.size_ml === size) ?? withData[withData.length - 1];
  const cv = (usd: number | null) => (usd == null ? null : usd * rate);
  const prices = current.points.map((p) => p.price_usd);

  const W = 280;
  const H = 44;
  const P = 4;
  let poly = '';
  let last: { x: number; y: number } | null = null;
  if (prices.length > 1) {
    const lo = Math.min(...prices);
    const hi = Math.max(...prices);
    const range = hi - lo || 1;
    const pts = prices.map((p, i) => ({
      x: P + (i / (prices.length - 1)) * (W - P * 2),
      y: H - P - ((p - lo) / range) * (H - P * 2),
    }));
    poly = pts.map((p) => `${p.x},${p.y}`).join(' ');
    last = pts[pts.length - 1];
  }

  return (
    <View style={styles.card}>
      <Text style={styles.header}>PRICES</Text>
      {withData.length > 1 && (
        <View style={styles.sizes}>
          {withData.map((s) => (
            <Chip key={s.size_ml} small label={`${s.size_ml} ml`} active={s.size_ml === current.size_ml}
                  onPress={() => setSize(s.size_ml)} />
          ))}
        </View>
      )}
      <Text style={styles.current}>
        {money(cv(current.latest_usd ?? current.msrp_usd), currency)}
        <Text style={styles.currentSub}>  {current.latest_usd != null ? 'latest seen' : 'reference price'} · {current.size_ml} ml</Text>
      </Text>
      {poly ? (
        <View style={styles.chart} accessible accessibilityLabel={`${prices.length} prices logged`}>
          <Svg width={W} height={H}>
            <Polyline points={poly} fill="none" stroke={colors.gold} strokeWidth={2} />
            {last && <Circle cx={last.x} cy={last.y} r={4} fill={colors.gold} />}
          </Svg>
        </View>
      ) : null}
      <View style={styles.stats}>
        <Stat label="LOW" value={money(cv(current.lowest_usd), currency)} color={colors.success} />
        <Stat label="HIGH" value={money(cv(current.highest_usd), currency)} color={colors.error} />
        <Stat label="REFERENCE" value={money(cv(current.msrp_usd), currency)} />
      </View>
    </View>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, color ? { color } : null]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.card, borderRadius: radius.base, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.base, marginBottom: spacing.base },
  header: { fontFamily: 'DMSans_500Medium', fontSize: 11, color: colors.textMuted, letterSpacing: 1.5, marginBottom: spacing.sm },
  sizes: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.sm, flexWrap: 'wrap' },
  current: { fontFamily: 'PlayfairDisplay_700Bold', fontSize: 22, color: colors.gold },
  currentSub: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: colors.textMuted },
  chart: { alignItems: 'center', marginVertical: spacing.sm },
  stats: { flexDirection: 'row', justifyContent: 'space-around', marginTop: spacing.sm },
  stat: { alignItems: 'center' },
  statLabel: { fontFamily: 'DMSans_500Medium', fontSize: 11, color: colors.textDark, letterSpacing: 1 },
  statValue: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: colors.text, marginTop: 2 },
});
