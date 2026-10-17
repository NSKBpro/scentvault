/**
 * ScentDNA Radar Chart — 6-axis radar for fragrance taste profile.
 *
 * Axes: Woody, Citrus, Aromatic, Oriental, Fresh, Floral
 * Uses react-native-svg for rendering.
 */

import { View, Text, StyleSheet } from 'react-native';
import Svg, { Polygon, Line, Circle, Text as SvgText } from 'react-native-svg';
import { colors } from '../theme/colors';

const AXES = ['Woody', 'Citrus', 'Aromatic', 'Oriental', 'Fresh', 'Floral'];
const SIZE = 200;
const CENTER = SIZE / 2;
const RADIUS = 75;

interface ScentDNARadarProps {
  data: Record<string, number>; // 0-100 per axis
}

export function ScentDNARadar({ data }: ScentDNARadarProps) {
  const angleStep = (2 * Math.PI) / AXES.length;
  const startAngle = -Math.PI / 2; // Start from top

  const getPoint = (index: number, value: number) => {
    const angle = startAngle + index * angleStep;
    const r = (value / 100) * RADIUS;
    return {
      x: CENTER + r * Math.cos(angle),
      y: CENTER + r * Math.sin(angle),
    };
  };

  // Grid rings at 25%, 50%, 75%, 100%
  const rings = [25, 50, 75, 100];

  // Data polygon points
  const dataPoints = AXES.map((axis, i) => {
    const key = axis.toLowerCase();
    const value = data[key] || 0;
    return getPoint(i, value);
  });
  const polygonPoints = dataPoints.map((p) => `${p.x},${p.y}`).join(' ');

  // Label positions (slightly outside the chart)
  const labelPoints = AXES.map((_, i) => {
    const angle = startAngle + i * angleStep;
    const r = RADIUS + 20;
    return {
      x: CENTER + r * Math.cos(angle),
      y: CENTER + r * Math.sin(angle),
    };
  });

  const hasData = Object.values(data).some((v) => v > 0);

  return (
    <View style={styles.container}>
      <Svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
        {/* Grid rings */}
        {rings.map((pct) => (
          <Circle
            key={pct}
            cx={CENTER}
            cy={CENTER}
            r={(pct / 100) * RADIUS}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={1}
          />
        ))}

        {/* Axis lines */}
        {AXES.map((_, i) => {
          const end = getPoint(i, 100);
          return (
            <Line
              key={i}
              x1={CENTER}
              y1={CENTER}
              x2={end.x}
              y2={end.y}
              stroke="rgba(255,255,255,0.06)"
              strokeWidth={1}
            />
          );
        })}

        {/* Data polygon */}
        {hasData && (
          <Polygon
            points={polygonPoints}
            fill="rgba(201,169,110,0.15)"
            stroke={colors.gold}
            strokeWidth={1.5}
          />
        )}

        {/* Axis labels */}
        {AXES.map((label, i) => (
          <SvgText
            key={label}
            x={labelPoints[i].x}
            y={labelPoints[i].y}
            fill={colors.textMuted}
            fontSize={8}
            textAnchor="middle"
            alignmentBaseline="middle"
          >
            {label}
          </SvgText>
        ))}
      </Svg>

      {!hasData && (
        <Text style={styles.emptyText}>
          Add fragrances to your collection to see your Scent DNA
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    paddingVertical: 8,
  },
  emptyText: {
    color: colors.textMuted,
    fontSize: 11,
    textAlign: 'center',
    marginTop: 4,
  },
});
