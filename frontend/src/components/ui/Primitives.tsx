// components/Primitives.jsx
// Atomic UI building blocks. All consume theme tokens.
// Add new primitives here — never inline one-off styles for repeated patterns.

import React, { useState, useRef, useEffect } from 'react';
import theme from '../theme';
const t = theme;

// ─────────────────────────────────────────────────────────────────────────────
// IconButton — square icon-only button
// ─────────────────────────────────────────────────────────────────────────────
export const IconButton = ({
    children, onClick, title, disabled = false,
    variant = 'ghost',  // ghost | solid | accent | danger
    size = 'md',        // xs | sm | md | lg
    active = false,
    style: sx = {},
}) => {
    const [hov, setHov] = useState(false);
    const sz = { xs: 22, sm: 26, md: 30, lg: 34 }[size] ?? 30;
    const fs = { xs: 11, sm: 12, md: 14, lg: 15 }[size] ?? 14;

    const bg = {
        ghost:  active ? t.colors.bgActive : hov && !disabled ? t.colors.bgHover : 'transparent',
        solid:  hov && !disabled ? t.colors.bgHover : t.colors.bgRaised,
        accent: active || (hov && !disabled) ? t.colors.accent : t.colors.accentSubtle,
        danger: hov && !disabled ? t.colors.dangerBg : 'transparent',
    }[variant] ?? 'transparent';

    const color = disabled ? t.colors.textDisabled : {
        ghost:  active ? t.colors.textPrimary : hov ? t.colors.textPrimary : t.colors.textSecondary,
        solid:  t.colors.textPrimary,
        accent: active || hov ? '#fff' : t.colors.accent,
        danger: t.colors.danger,
    }[variant] ?? t.colors.textSecondary;

    return (
        <button
            title={title}
            onClick={disabled ? undefined : onClick}
            onMouseEnter={() => setHov(true)}
            onMouseLeave={() => setHov(false)}
            style={{
                width: sz, height: sz, borderRadius: t.radius.sm,
                border: active && variant === 'ghost' ? `1px solid ${t.colors.borderMid}` : '1px solid transparent',
                backgroundColor: bg, color,
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                cursor: disabled ? 'not-allowed' : 'pointer',
                flexShrink: 0, fontSize: fs, lineHeight: 1,
                transition: t.t.fast, fontFamily: t.fonts.ui, padding: 0,
                ...sx,
            }}
        >{children}</button>
    );
};

// ─────────────────────────────────────────────────────────────────────────────
// Button — text button with optional leading icon
// ─────────────────────────────────────────────────────────────────────────────
export const Button = ({
    children, onClick, title, disabled = false, icon,
    variant = 'ghost',  // ghost | solid | accent | danger | success
    size = 'md',        // sm | md | lg
    style: sx = {},
}) => {
    const [hov, setHov] = useState(false);
    const h  = { sm: 24, md: 28, lg: 32 }[size] ?? 28;
    const fs = { sm: 11, md: 12, lg: 13 }[size] ?? 12;
    const px = { sm: 8,  md: 10, lg: 14 }[size] ?? 10;

    const styles = {
        ghost:   { bg: hov && !disabled ? t.colors.bgHover   : 'transparent',    color: disabled ? t.colors.textDisabled : hov ? t.colors.textPrimary : t.colors.textSecondary, border: '1px solid transparent' },
        solid:   { bg: hov && !disabled ? t.colors.bgHover   : t.colors.bgRaised, color: disabled ? t.colors.textDisabled : t.colors.textPrimary, border: `1px solid ${t.colors.border}` },
        accent:  { bg: hov && !disabled ? t.colors.accentHover: t.colors.accent,  color: '#fff', border: 'none' },
        danger:  { bg: hov && !disabled ? '#b84444'          : t.colors.danger,   color: '#fff', border: 'none' },
        success: { bg: hov && !disabled ? '#35b48e'          : t.colors.success,  color: '#0a1f17', border: 'none' },
    };
    const s = styles[variant] ?? styles.ghost;

    return (
        <button
            title={title}
            onClick={disabled ? undefined : onClick}
            onMouseEnter={() => setHov(true)}
            onMouseLeave={() => setHov(false)}
            style={{
                height: h, padding: `0 ${px}px`, borderRadius: t.radius.sm,
                border: s.border, backgroundColor: s.bg, color: s.color,
                display: 'inline-flex', alignItems: 'center', gap: '5px',
                fontFamily: t.fonts.ui, fontSize: fs, fontWeight: '500',
                cursor: disabled ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
                flexShrink: 0, transition: t.t.fast, outline: 'none',
                ...sx,
            }}
        >
            {icon && <span style={{ fontSize: fs + 1, lineHeight: 1, opacity: 0.85 }}>{icon}</span>}
            {children}
        </button>
    );
};

// ─────────────────────────────────────────────────────────────────────────────
// Divider — thin separator line
// ─────────────────────────────────────────────────────────────────────────────
export const Divider = ({ vertical = true, style: sx = {} }) => (
    <div style={{
        width:  vertical ? '1px' : '100%',
        height: vertical ? '16px' : '1px',
        backgroundColor: t.colors.border,
        flexShrink: 0,
        margin: vertical ? '0 3px' : '3px 0',
        ...sx,
    }} />
);

// ─────────────────────────────────────────────────────────────────────────────
// Kbd — keyboard shortcut badge
// ─────────────────────────────────────────────────────────────────────────────
export const Kbd = ({ children }) => (
    <span style={{
        fontSize: '10px', fontFamily: t.fonts.mono,
        color: t.colors.textMuted,
        backgroundColor: t.colors.bgBase,
        border: `1px solid ${t.colors.border}`,
        borderRadius: t.radius.xs,
        padding: '1px 4px', lineHeight: 1.4,
    }}>{children}</span>
);

// ─────────────────────────────────────────────────────────────────────────────
// DropdownMenu — cascading menu, reused by MenuBar and context menus
// items: Array<{ label, icon, shortcut, onClick, disabled, separator, submenu }>
// ─────────────────────────────────────────────────────────────────────────────
export const DropdownMenu = ({ items, style: sx = {}, onClose }) => {
    const menuRef = useRef(null);

    useEffect(() => {
        const handler = (e) => {
            if (menuRef.current && !menuRef.current.contains(e.target)) onClose?.();
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [onClose]);

    return (
        <div
            ref={menuRef}
            style={{
                position: 'absolute',
                minWidth: '220px',
                backgroundColor: t.colors.bgRaised,
                border: `1px solid ${t.colors.borderMid}`,
                borderRadius: t.radius.md,
                boxShadow: t.shadow.menu,
                padding: '4px',
                zIndex: 9000,
                animation: 'slideDown 0.1s ease',
                fontFamily: t.fonts.ui,
                ...sx,
            }}
        >
            {items.map((item, i) => {
                if (item.separator) return (
                    <div key={i} style={{ height: '1px', backgroundColor: t.colors.border, margin: '3px 0' }} />
                );
                return (
                    <MenuItem key={i} item={item} onClose={onClose} />
                );
            })}
        </div>
    );
};

const MenuItem = ({ item, onClose }) => {
    const [hov, setHov] = useState(false);
    const [subOpen, setSubOpen] = useState(false);
    const hasSubmenu = item.submenu && item.submenu.length > 0;

    return (
        <div
            style={{ position: 'relative' }}
            onMouseEnter={() => { setHov(true); if (hasSubmenu) setSubOpen(true); }}
            onMouseLeave={() => { setHov(false); if (hasSubmenu) setSubOpen(false); }}
        >
            <div
                onClick={() => {
                    if (item.disabled || hasSubmenu) return;
                    item.onClick?.();
                    onClose?.();
                }}
                style={{
                    display: 'flex', alignItems: 'center', gap: '8px',
                    padding: '5px 8px', borderRadius: t.radius.sm,
                    backgroundColor: hov && !item.disabled ? t.colors.bgHover : 'transparent',
                    color: item.disabled ? t.colors.textDisabled : t.colors.textPrimary,
                    cursor: item.disabled ? 'not-allowed' : 'pointer',
                    fontSize: '12px', fontWeight: '400',
                    transition: t.t.fast,
                }}
            >
                <span style={{ width: '16px', textAlign: 'center', fontSize: '13px', opacity: 0.7, flexShrink: 0 }}>
                    {item.icon ?? ''}
                </span>
                <span style={{ flex: 1 }}>{item.label}</span>
                {item.shortcut && <Kbd>{item.shortcut}</Kbd>}
                {hasSubmenu && <span style={{ color: t.colors.textMuted, fontSize: '10px' }}>›</span>}
            </div>
            {hasSubmenu && subOpen && (
                <div style={{ position: 'absolute', left: '100%', top: '-4px' }}>
                    <DropdownMenu items={item.submenu} onClose={onClose} />
                </div>
            )}
        </div>
    );
};

// ─────────────────────────────────────────────────────────────────────────────
// Tag / Badge
// ─────────────────────────────────────────────────────────────────────────────
export const Tag = ({ children, color = t.colors.accent }) => (
    <span style={{
        fontSize: '10px', fontWeight: '600',
        color, backgroundColor: `${color}18`,
        border: `1px solid ${color}30`,
        borderRadius: t.radius.pill, padding: '1px 6px',
        fontFamily: t.fonts.mono, letterSpacing: '0.02em',
        lineHeight: 1.5,
    }}>{children}</span>
);

// ─────────────────────────────────────────────────────────────────────────────
// Tooltip (simple title-based, can be upgraded)
// ─────────────────────────────────────────────────────────────────────────────
export const Tooltip = ({ children, text }) => (
    <span title={text} style={{ display: 'contents' }}>{children}</span>
);

// ─────────────────────────────────────────────────────────────────────────────
// PanelSection — labeled section inside a properties panel
// ─────────────────────────────────────────────────────────────────────────────
export const PanelSection = ({ title, children, collapsible = false }) => {
    const [open, setOpen] = useState(true);
    return (
        <div style={{ borderBottom: `1px solid ${t.colors.border}` }}>
            <div
                onClick={collapsible ? () => setOpen(o => !o) : undefined}
                style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '8px 12px 6px',
                    cursor: collapsible ? 'pointer' : 'default',
                }}
            >
                <span style={{
                    fontSize: '10px', fontWeight: '600', letterSpacing: '0.08em',
                    textTransform: 'uppercase', color: t.colors.textMuted,
                    fontFamily: t.fonts.ui,
                }}>{title}</span>
                {collapsible && (
                    <span style={{ color: t.colors.textMuted, fontSize: '10px', transition: t.t.fast, transform: open ? 'rotate(0deg)' : 'rotate(-90deg)', display: 'inline-block' }}>▾</span>
                )}
            </div>
            {open && (
                <div style={{ padding: '0 12px 10px' }}>{children}</div>
            )}
        </div>
    );
};

// ─────────────────────────────────────────────────────────────────────────────
// PropRow — label + value row in properties panel
// ─────────────────────────────────────────────────────────────────────────────
export const PropRow = ({ label, children }) => (
    <div style={{
        display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', gap: '8px',
        marginBottom: '6px',
    }}>
        <span style={{ fontSize: '11px', color: t.colors.textSecondary, flexShrink: 0, fontFamily: t.fonts.ui }}>
            {label}
        </span>
        <span style={{ fontSize: '11px', color: t.colors.textPrimary, fontFamily: t.fonts.mono, textAlign: 'right' }}>
            {children}
        </span>
    </div>
);