/**
 * ScentVault Theme Provider.
 *
 * - Loads Playfair Display and DM Sans via expo-font
 * - Provides theme context to all children
 * - Shows splash/loading state until fonts are ready
 */

import React, { createContext, useContext, useEffect } from 'react';
import { ActivityIndicator, StatusBar, View } from 'react-native';
import {
  useFonts,
  PlayfairDisplay_400Regular,
  PlayfairDisplay_700Bold,
} from '@expo-google-fonts/playfair-display';
import {
  DMSans_400Regular,
  DMSans_500Medium,
  DMSans_700Bold,
} from '@expo-google-fonts/dm-sans';
import * as SplashScreen from 'expo-splash-screen';

import { colors } from './colors';
import { typography, fonts } from './typography';
import { spacing, radius } from './spacing';

// Keep splash visible while fonts load
SplashScreen.preventAutoHideAsync().catch(() => {});

export const theme = {
  colors,
  typography,
  fonts,
  spacing,
  radius,
} as const;

export type Theme = typeof theme;

const ThemeContext = createContext<Theme>(theme);

export const useTheme = () => useContext(ThemeContext);

interface ThemeProviderProps {
  children: React.ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [fontsLoaded] = useFonts({
    PlayfairDisplay_400Regular,
    PlayfairDisplay_700Bold,
    DMSans_400Regular,
    DMSans_500Medium,
    DMSans_700Bold,
  });

  useEffect(() => {
    if (fontsLoaded) {
      SplashScreen.hideAsync().catch(() => {});
    }
  }, [fontsLoaded]);

  if (!fontsLoaded) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.background, justifyContent: 'center', alignItems: 'center' }}>
        <StatusBar barStyle="light-content" backgroundColor={colors.background} />
        <ActivityIndicator color={colors.gold} size="large" />
      </View>
    );
  }

  return (
    <ThemeContext.Provider value={theme}>
      <StatusBar barStyle="light-content" backgroundColor={colors.background} />
      {children}
    </ThemeContext.Provider>
  );
}
