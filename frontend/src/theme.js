// theme.js — Single source of truth for all design tokens.
// Edit here to retheme the entire application instantly.

export const theme = {

    // ── Typography ────────────────────────────────────────────────────────────
    fonts: {
        ui:   "'DM Sans', 'Helvetica Neue', sans-serif",
        mono: "'JetBrains Mono', 'Fira Code', monospace",
    },

    // ── Color Palette ─────────────────────────────────────────────────────────
    colors: {
        // App chrome layers
        chrome:        '#0e1117',   // menu bar — deepest
        bgBase:        '#13161d',   // body background
        bgSurface:     '#191d26',   // panels, sidebars
        bgRaised:      '#20242f',   // cards, inputs
        bgHover:       '#272c38',   // hover
        bgActive:      '#2e3444',   // pressed
        bgCanvas:      '#d8dce4',   // document canvas

        // Borders
        border:        'rgba(255,255,255,0.055)',
        borderMid:     'rgba(255,255,255,0.09)',
        borderStrong:  'rgba(255,255,255,0.15)',

        // Text
        textPrimary:   '#e6e9f0',
        textSecondary: '#7a8499',
        textMuted:     '#404858',
        textDisabled:  '#2e3444',

        // Primary accent — clear blue, not overused purple
        accent:        '#4f7ef7',
        accentHover:   '#6b93f9',
        accentActive:  '#3d6be0',
        accentSubtle:  'rgba(79,126,247,0.1)',
        accentGlow:    '0 0 0 2px rgba(79,126,247,0.4)',

        // Tool colors
        highlight:     '#e0aa3e',
        highlightBg:   'rgba(224,170,62,0.2)',
        redact:        '#d45c5c',
        redactBg:      'rgba(212,92,92,0.18)',
        crop:          '#d97c3a',
        cropBg:        'rgba(217,124,58,0.18)',
        select:        '#4f7ef7',
        selectBg:      'rgba(79,126,247,0.18)',
        link:          '#3ecba0',
        linkBg:        'rgba(62,203,160,0.15)',

        // Semantic
        success:       '#3ecba0',
        successBg:     'rgba(62,203,160,0.12)',
        danger:        '#d45c5c',
        dangerBg:      'rgba(212,92,92,0.12)',
        warning:       '#e0aa3e',
        warningBg:     'rgba(224,170,62,0.12)',
    },

    // ── Spacing ───────────────────────────────────────────────────────────────
    sp: (n) => `${n * 4}px`,   // sp(2) = 8px, sp(3) = 12px, etc.

    // ── Radii ─────────────────────────────────────────────────────────────────
    radius: {
        xs:   '3px',
        sm:   '5px',
        md:   '6px',
        lg:   '9px',
        xl:   '13px',
        pill: '999px',
    },

    // ── Shadows ───────────────────────────────────────────────────────────────
    shadow: {
        xs:   '0 1px 3px rgba(0,0,0,0.3)',
        sm:   '0 2px 8px rgba(0,0,0,0.4)',
        md:   '0 4px 16px rgba(0,0,0,0.5)',
        lg:   '0 8px 32px rgba(0,0,0,0.6)',
        menu: '0 8px 24px rgba(0,0,0,0.65), 0 0 0 1px rgba(255,255,255,0.07)',
        page: '0 2px 16px rgba(0,0,0,0.28)',
        pageHov: '0 6px 32px rgba(0,0,0,0.45)',
    },

    // ── Layout ────────────────────────────────────────────────────────────────
    layout: {
        menuBarH:    '26px',
        tabBarH:     '34px',
        toolbarH:    '42px',
        statusBarH:  '22px',
        leftRailW:   '38px',
        leftDrawerW: '216px',
        rightPanelW: '252px',
        thumbW:      138,
    },

    // ── Transitions ───────────────────────────────────────────────────────────
    t: {
        fast: 'all 0.1s ease',
        mid:  'all 0.17s ease',
        slow: 'all 0.26s ease',
    },
};

export function injectGlobalStyles() {
    if (document.getElementById('app-global-styles')) return;
    const el = document.createElement('style');
    el.id = 'app-global-styles';
    const c = theme.colors;
    el.textContent = `
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        html, body, #root {
            height: 100%;
            background: ${c.chrome};
            font-family: ${theme.fonts.ui};
            color: ${c.textPrimary};
            -webkit-font-smoothing: antialiased;
        }

        /* Scrollbars */
        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: ${c.bgActive}; border-radius: 99px; }
        ::-webkit-scrollbar-thumb:hover { background: ${c.textMuted}; }

        /* Animations */
        @keyframes spin        { to { transform: rotate(360deg); } }
        @keyframes fadeIn      { from { opacity: 0; } to { opacity: 1; } }
        @keyframes slideDown   { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes slideUp     { from { opacity: 0; transform: translateY(6px);  } to { opacity: 1; transform: translateY(0); } }
        @keyframes slideRight  { from { opacity: 0; transform: translateX(-8px); } to { opacity: 1; transform: translateX(0); } }
        @keyframes pageCtrlIn  { from { opacity: 0; transform: translateX(-50%) translateY(4px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }

        /* Focus ring */
        button:focus-visible { outline: 2px solid ${c.accent}; outline-offset: 1px; }
        input:focus { outline: none; }

        /* Prevent text selection on UI chrome */
        .no-select { user-select: none; }
    `;
    document.head.appendChild(el);
}

export default theme;