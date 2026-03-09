// frontend/src/theme/themes.ts
// All named themes. Each theme is a complete token map.
// Add new themes here — they will automatically appear in the Theme menu.

export interface ThemeTokens {
  colors: {
    // Surfaces
    bgBase:       string;
    bgRaised:     string;
    bgHover:      string;
    bgActive:     string;
    // Borders
    border:       string;
    borderMid:    string;
    // Text
    textPrimary:  string;
    textSecondary:string;
    textMuted:    string;
    textDisabled: string;
    // Accent / brand
    accent:       string;
    accentSubtle: string;
    accentHover:  string;
    // Semantic
    danger:       string;
    dangerBg:     string;
    success:      string;
  };
  radius: { xs: string; sm: string; md: string; lg: string; pill: string };
  fonts:  { ui: string; mono: string };
  shadow: { menu: string; panel: string };
  t:      { fast: string };
}

export type ThemeId =
  | 'dark'
  | 'darker'
  | 'light'
  | 'solarized'
  | 'nord'
  | 'monokai';

export interface ThemeDef {
  id:    ThemeId;
  label: string;
  tokens: ThemeTokens;
}

// ── Shared structural tokens (same across all themes) ────────────────────────

const shared = {
  radius: { xs: '3px', sm: '5px', md: '8px', lg: '12px', pill: '999px' },
  fonts:  { ui: "'Inter', 'Segoe UI', system-ui, sans-serif", mono: "'JetBrains Mono', 'Fira Code', monospace" },
  t:      { fast: 'all 0.1s ease' },
};

// ── Theme definitions ─────────────────────────────────────────────────────────

export const THEMES: ThemeDef[] = [
  {
    id: 'dark',
    label: 'Dark',
    tokens: {
      ...shared,
      colors: {
        bgBase:        '#1e2327',
        bgRaised:      '#2d3338',
        bgHover:       '#3d4449',
        bgActive:      '#3d4449',
        border:        'rgba(255,255,255,0.06)',
        borderMid:     'rgba(255,255,255,0.10)',
        textPrimary:   '#e8eaed',
        textSecondary: '#9aa0a6',
        textMuted:     '#6b7280',
        textDisabled:  '#4b5563',
        accent:        '#4a90e2',
        accentSubtle:  'rgba(74,144,226,0.15)',
        accentHover:   '#3a7bd5',
        danger:        '#ef4444',
        dangerBg:      'rgba(239,68,68,0.15)',
        success:       '#22c55e',
      },
      shadow: {
        menu:  '0 8px 24px rgba(0,0,0,0.5)',
        panel: '0 2px 8px rgba(0,0,0,0.3)',
      },
    },
  },
  {
    id: 'darker',
    label: 'Darker',
    tokens: {
      ...shared,
      colors: {
        bgBase:        '#0d1117',
        bgRaised:      '#161b22',
        bgHover:       '#21262d',
        bgActive:      '#30363d',
        border:        'rgba(255,255,255,0.05)',
        borderMid:     'rgba(255,255,255,0.08)',
        textPrimary:   '#c9d1d9',
        textSecondary: '#8b949e',
        textMuted:     '#6e7681',
        textDisabled:  '#484f58',
        accent:        '#58a6ff',
        accentSubtle:  'rgba(88,166,255,0.15)',
        accentHover:   '#388bfd',
        danger:        '#f85149',
        dangerBg:      'rgba(248,81,73,0.15)',
        success:       '#3fb950',
      },
      shadow: {
        menu:  '0 8px 32px rgba(0,0,0,0.7)',
        panel: '0 2px 8px rgba(0,0,0,0.5)',
      },
    },
  },
  {
    id: 'light',
    label: 'Light',
    tokens: {
      ...shared,
      colors: {
        bgBase:        '#f0f2f5',
        bgRaised:      '#ffffff',
        bgHover:       '#e8eaed',
        bgActive:      '#dde1e7',
        border:        'rgba(0,0,0,0.08)',
        borderMid:     'rgba(0,0,0,0.12)',
        textPrimary:   '#1a1a2e',
        textSecondary: '#4b5563',
        textMuted:     '#9ca3af',
        textDisabled:  '#d1d5db',
        accent:        '#2563eb',
        accentSubtle:  'rgba(37,99,235,0.10)',
        accentHover:   '#1d4ed8',
        danger:        '#dc2626',
        dangerBg:      'rgba(220,38,38,0.08)',
        success:       '#16a34a',
      },
      shadow: {
        menu:  '0 8px 24px rgba(0,0,0,0.12)',
        panel: '0 2px 8px rgba(0,0,0,0.08)',
      },
    },
  },
  {
    id: 'solarized',
    label: 'Solarized',
    tokens: {
      ...shared,
      colors: {
        bgBase:        '#002b36',
        bgRaised:      '#073642',
        bgHover:       '#094652',
        bgActive:      '#0d5060',
        border:        'rgba(101,123,131,0.25)',
        borderMid:     'rgba(101,123,131,0.40)',
        textPrimary:   '#eee8d5',
        textSecondary: '#93a1a1',
        textMuted:     '#657b83',
        textDisabled:  '#4a6570',
        accent:        '#268bd2',
        accentSubtle:  'rgba(38,139,210,0.18)',
        accentHover:   '#1a7abf',
        danger:        '#dc322f',
        dangerBg:      'rgba(220,50,47,0.18)',
        success:       '#859900',
      },
      shadow: {
        menu:  '0 8px 28px rgba(0,0,0,0.6)',
        panel: '0 2px 8px rgba(0,0,0,0.4)',
      },
    },
  },
  {
    id: 'nord',
    label: 'Nord',
    tokens: {
      ...shared,
      colors: {
        bgBase:        '#2e3440',
        bgRaised:      '#3b4252',
        bgHover:       '#434c5e',
        bgActive:      '#4c566a',
        border:        'rgba(216,222,233,0.08)',
        borderMid:     'rgba(216,222,233,0.14)',
        textPrimary:   '#eceff4',
        textSecondary: '#d8dee9',
        textMuted:     '#9099a8',
        textDisabled:  '#616e7f',
        accent:        '#88c0d0',
        accentSubtle:  'rgba(136,192,208,0.15)',
        accentHover:   '#6bafc2',
        danger:        '#bf616a',
        dangerBg:      'rgba(191,97,106,0.18)',
        success:       '#a3be8c',
      },
      shadow: {
        menu:  '0 8px 28px rgba(0,0,0,0.5)',
        panel: '0 2px 8px rgba(0,0,0,0.3)',
      },
    },
  },
  {
    id: 'monokai',
    label: 'Monokai',
    tokens: {
      ...shared,
      colors: {
        bgBase:        '#272822',
        bgRaised:      '#3e3d32',
        bgHover:       '#49483e',
        bgActive:      '#75715e',
        border:        'rgba(255,255,255,0.07)',
        borderMid:     'rgba(255,255,255,0.12)',
        textPrimary:   '#f8f8f2',
        textSecondary: '#cfcfc2',
        textMuted:     '#75715e',
        textDisabled:  '#4e4d45',
        accent:        '#a6e22e',
        accentSubtle:  'rgba(166,226,46,0.15)',
        accentHover:   '#8fc026',
        danger:        '#f92672',
        dangerBg:      'rgba(249,38,114,0.15)',
        success:       '#a6e22e',
      },
      shadow: {
        menu:  '0 8px 28px rgba(0,0,0,0.55)',
        panel: '0 2px 8px rgba(0,0,0,0.35)',
      },
    },
  },
];

export const THEMES_BY_ID = Object.fromEntries(THEMES.map(t => [t.id, t])) as Record<ThemeId, ThemeDef>;
export const DEFAULT_THEME_ID: ThemeId = 'dark';