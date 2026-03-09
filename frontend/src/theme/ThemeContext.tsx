// frontend/src/theme/ThemeContext.tsx
// Provides the active theme tokens to the entire app.
// Wrap <App> in <ThemeProvider> and consume via useTheme() anywhere.

import React, { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import { THEMES_BY_ID, DEFAULT_THEME_ID, type ThemeId, type ThemeTokens } from './themes';

interface ThemeContextValue {
  themeId:   ThemeId;
  theme:     ThemeTokens;
  setTheme:  (id: ThemeId) => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  themeId:  DEFAULT_THEME_ID,
  theme:    THEMES_BY_ID[DEFAULT_THEME_ID].tokens,
  setTheme: () => {},
});

const STORAGE_KEY = 'pdf-editor-theme';

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [themeId, setThemeIdState] = useState<ThemeId>(() => {
    const saved = localStorage.getItem(STORAGE_KEY) as ThemeId | null;
    return saved && THEMES_BY_ID[saved] ? saved : DEFAULT_THEME_ID;
  });

  const setTheme = useCallback((id: ThemeId) => {
    setThemeIdState(id);
    localStorage.setItem(STORAGE_KEY, id);
  }, []);

  return (
    <ThemeContext.Provider value={{ themeId, theme: THEMES_BY_ID[themeId].tokens, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}