// frontend/src/theme/index.ts
// Re-exports everything theme-related.
// For legacy imports of the static `theme` object (e.g. in Primitives.tsx before migration),
// this module no longer exports a static default. Primitives.tsx now uses useTheme() directly.

export { useTheme, ThemeProvider } from './ThemeContext';
export { THEMES, THEMES_BY_ID, DEFAULT_THEME_ID } from './themes';
export type { ThemeId, ThemeTokens, ThemeDef } from './themes';