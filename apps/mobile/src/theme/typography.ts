/**
 * ScentVault typography.
 *
 * Playfair Display (serif) for headings/titles.
 * DM Sans (sans-serif) for body text and UI.
 * Falls back to system fonts if custom fonts haven't loaded.
 */

export const fonts = {
  serif: 'PlayfairDisplay_700Bold',
  serifRegular: 'PlayfairDisplay_400Regular',
  sans: 'DMSans_400Regular',
  sansMedium: 'DMSans_500Medium',
  sansBold: 'DMSans_700Bold',

  // System fallbacks (used before fonts load)
  serifFallback: 'serif',
  sansFallback: 'System',
} as const;

export const typography = {
  // Headings (Playfair Display)
  h1: {
    fontFamily: fonts.serif,
    fontSize: 28,
    lineHeight: 36,
  },
  h2: {
    fontFamily: fonts.serif,
    fontSize: 22,
    lineHeight: 30,
  },
  h3: {
    fontFamily: fonts.serif,
    fontSize: 18,
    lineHeight: 26,
  },

  // Body (DM Sans)
  bodyLarge: {
    fontFamily: fonts.sans,
    fontSize: 16,
    lineHeight: 24,
  },
  body: {
    fontFamily: fonts.sans,
    fontSize: 14,
    lineHeight: 22,
  },
  bodySmall: {
    fontFamily: fonts.sans,
    fontSize: 12,
    lineHeight: 18,
  },

  // UI text
  button: {
    fontFamily: fonts.sansMedium,
    fontSize: 15,
    lineHeight: 20,
  },
  caption: {
    fontFamily: fonts.sans,
    fontSize: 11,
    lineHeight: 16,
  },
  label: {
    fontFamily: fonts.sansMedium,
    fontSize: 13,
    lineHeight: 18,
  },
  tabLabel: {
    fontFamily: fonts.sansMedium,
    fontSize: 11,
  },
} as const;
