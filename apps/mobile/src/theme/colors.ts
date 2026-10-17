/**
 * ScentVault color palette.
 *
 * Dark luxury theme: deep navy background with gold accents.
 */

export const colors = {
  // Backgrounds
  background: '#0D0D1A',
  card: '#1A1A2E',
  cardBorder: 'rgba(255, 255, 255, 0.08)', // visible on #1A1A2E (was 2.4% — invisible)
  inputBg: '#0D0D1A',

  // Brand
  gold: '#C9A96E',
  goldLight: 'rgba(201, 169, 110, 0.15)',
  goldDim: 'rgba(201, 169, 110, 0.6)',

  // Text
  text: '#F0ECE2',
  textSecondary: '#AAAAAA',
  textMuted: '#9A9AA8', // ≥ 4.5:1 on background
  textDark: '#8A8A99', // was #555 (2.6:1 contrast); now ≥ 4.5:1

  // Semantic
  success: '#6ECF8E',
  error: '#E05555',
  warning: '#E0A855',
  info: '#5EA5E0',

  // Tab bar
  tabActive: '#C9A96E',
  tabInactive: '#8A8A99',
  tabBarBg: '#0D0D1A',

  // Misc
  white: '#FFFFFF',
  black: '#000000',
  transparent: 'transparent',
  overlay: 'rgba(0, 0, 0, 0.6)',
  separator: 'rgba(255, 255, 255, 0.08)',
  skeleton: 'rgba(255, 255, 255, 0.06)',
} as const;

export type ColorKey = keyof typeof colors;
