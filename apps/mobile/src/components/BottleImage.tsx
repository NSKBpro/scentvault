/** Bottle image with a brand-initial fallback (image_url used to be ignored everywhere). */
import { useState } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import { colors } from '../theme/colors';

interface Props {
  uri: string | null | undefined;
  brand: string | null | undefined;
  size?: number;
  rounded?: number;
}

export function BottleImage({ uri, brand, size = 50, rounded = 12 }: Props) {
  const [failed, setFailed] = useState(false);
  const box = { width: size, height: size, borderRadius: rounded };
  if (uri && !failed) {
    return (
      <View style={[styles.box, box]}>
        <Image source={{ uri }} style={[box, { resizeMode: 'contain' }]} onError={() => setFailed(true)}
               accessibilityIgnoresInvertColors accessible={false} />
      </View>
    );
  }
  return (
    <View style={[styles.box, box]} accessible={false}>
      <Text style={[styles.initial, { fontSize: size * 0.4 }]}>{brand?.[0]?.toUpperCase() ?? '?'}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  box: { backgroundColor: colors.background, justifyContent: 'center', alignItems: 'center', overflow: 'hidden' },
  initial: { fontFamily: 'PlayfairDisplay_700Bold', color: colors.gold },
});
