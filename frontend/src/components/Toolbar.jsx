// components/Toolbar.jsx
// Compact contextual toolbar — tools, zoom, undo/redo, read-aloud.
// Intentionally NOT the place for File/Export — those live in the MenuBar.

import React, { useState } from 'react';
import { TOOLS, TOOL_ICONS } from '../tools';
import theme from '../theme';
import { IconButton, Divider, Button } from './Primitives';
const t = theme;

// Tool accent colors — one per tool
const TOOL_ACCENT = {
    [TOOLS.SELECT]:    t.colors.accent,
    [TOOLS.TEXT]:      t.colors.accent,
    [TOOLS.HIGHLIGHT]: t.colors.highlight,
    [TOOLS.REDACT]:    t.colors.redact,
    [TOOLS.CROP]:      t.colors.crop,
    [TOOLS.LINK]:      t.colors.link,
};

const ToolBtn = ({ tool, isActive, onClick }) => {
    const [hov, setHov] = useState(false);
    const info   = TOOL_ICONS[tool];
    const accent = TOOL_ACCENT[tool] ?? t.colors.accent;

    return (
        <button
            onClick={onClick}
            title={`${info.label}${info.key ? ` (${info.key})` : ''}`}
            onMouseEnter={() => setHov(true)}
            onMouseLeave={() => setHov(false)}
            style={{
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', gap: '2px',
                padding: '0 10px', height: '100%',
                minWidth: '46px',
                border: 'none',
                borderBottom: isActive ? `2px solid ${accent}` : '2px solid transparent',
                backgroundColor: isActive
                    ? `${accent}0f`
                    : hov ? t.colors.bgHover : 'transparent',
                color: isActive ? accent : hov ? t.colors.textPrimary : t.colors.textSecondary,
                cursor: 'pointer',
                transition: t.t.fast,
                fontFamily: t.fonts.ui,
                flexShrink: 0,
            }}
        >
            <span style={{ fontSize: '14px', lineHeight: 1 }}>{info.icon}</span>
            <span style={{ fontSize: '9px', fontWeight: isActive ? '600' : '400', letterSpacing: '0.03em' }}>
                {info.label}
            </span>
        </button>
    );
};

const ZoomInput = ({ scale, onIn, onOut, onReset }) => {
    const [hov, setHov] = useState(false);
    return (
        <div
            onMouseEnter={() => setHov(true)}
            onMouseLeave={() => setHov(false)}
            style={{
                display: 'flex', alignItems: 'center', gap: '1px',
                backgroundColor: hov ? t.colors.bgHover : t.colors.bgRaised,
                border: `1px solid ${t.colors.border}`,
                borderRadius: t.radius.sm,
                height: '26px', overflow: 'hidden',
                transition: t.t.fast,
            }}
        >
            <button onClick={onOut} title="Zoom out" disabled={scale <= 0.25} style={zoomBtnStyle}>−</button>
            <button onClick={onReset} title="Reset to 100%" style={{ ...zoomBtnStyle, minWidth: '44px', fontFamily: t.fonts.mono, fontSize: '11px', fontWeight: '600', color: t.colors.textPrimary }}>
                {Math.round(scale * 100)}%
            </button>
            <button onClick={onIn} title="Zoom in" disabled={scale >= 4.0} style={zoomBtnStyle}>+</button>
        </div>
    );
};

const zoomBtnStyle = {
    height: '100%', padding: '0 6px',
    border: 'none', background: 'transparent',
    color: t.colors.textSecondary, cursor: 'pointer',
    fontSize: '13px', fontFamily: t.fonts.ui,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
};

export const Toolbar = ({
    activeTool, onToolChange,
    scale, onZoomIn, onZoomOut, onZoomReset,
    onUndo, onRedo,
    onReadPage, onReadSelection, hasSelection,
    ttsActive,
    pageInfo,        // { current, total } 
}) => {
    return (
        <div
            className="no-select"
            style={{
                height: t.layout.toolbarH,
                backgroundColor: t.colors.bgSurface,
                borderBottom: `1px solid ${t.colors.border}`,
                display: 'flex',
                alignItems: 'stretch',
                gap: '0',
                flexShrink: 0,
                paddingLeft: '4px',
            }}
        >
            {/* Undo / Redo */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '2px', padding: '0 6px', borderRight: `1px solid ${t.colors.border}` }}>
                <IconButton onClick={onUndo} title="Undo (Ctrl+Z)" size="sm">
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M4 3L1.5 5.5 4 8"/><path d="M1.5 5.5h6a4 4 0 1 1 0 8H4"/>
                    </svg>
                </IconButton>
                <IconButton onClick={onRedo} title="Redo (Ctrl+Y)" size="sm">
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M10 3l2.5 2.5L10 8"/><path d="M12.5 5.5h-6a4 4 0 1 0 0 8H10"/>
                    </svg>
                </IconButton>
            </div>

            {/* Tools */}
            <div style={{ display: 'flex', alignItems: 'stretch', borderRight: `1px solid ${t.colors.border}` }}>
                {Object.values(TOOLS).map(tool => (
                    <ToolBtn
                        key={tool}
                        tool={tool}
                        isActive={activeTool === tool}
                        onClick={() => onToolChange(tool)}
                    />
                ))}
            </div>

            {/* Read aloud */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '2px', padding: '0 8px', borderRight: `1px solid ${t.colors.border}` }}>
                <span style={{ fontSize: '10px', color: t.colors.textMuted, marginRight: '2px', letterSpacing: '0.06em', textTransform: 'uppercase' }}>Read</span>
                <IconButton
                    onClick={onReadPage}
                    disabled={ttsActive}
                    title="Read current page aloud"
                    size="sm"
                >
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
                        <path d="M2 4.5H0.5a.5.5 0 0 0-.5.5v4a.5.5 0 0 0 .5.5H2l3 2.5V2L2 4.5z"/>
                        <path d="M9.5 7a2.5 2.5 0 0 0-1.5-2.3v4.6A2.5 2.5 0 0 0 9.5 7z" opacity=".6"/>
                        <path d="M11.5 7a4.5 4.5 0 0 0-2.5-4v8a4.5 4.5 0 0 0 2.5-4z" opacity=".35"/>
                    </svg>
                </IconButton>
                <IconButton
                    onClick={onReadSelection}
                    disabled={ttsActive || !hasSelection}
                    title="Read selected text"
                    size="sm"
                    style={{ opacity: hasSelection ? 1 : 0.4 }}
                >
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
                        <rect x="1" y="2" width="12" height="1.5" rx=".75" opacity=".4"/>
                        <rect x="1" y="5.5" width="7" height="1.5" rx=".75" opacity=".4"/>
                        <rect x="1" y="9" width="9" height="1.5" rx=".75" opacity=".4"/>
                        <path d="M10 8.5l2.5 1.5L10 11.5v-3z"/>
                    </svg>
                </IconButton>
            </div>

            {/* Zoom */}
            <div style={{ display: 'flex', alignItems: 'center', padding: '0 10px', borderRight: `1px solid ${t.colors.border}` }}>
                <ZoomInput scale={scale} onIn={onZoomIn} onOut={onZoomOut} onReset={onZoomReset} />
            </div>

            {/* Page indicator */}
            {pageInfo && (
                <div style={{ display: 'flex', alignItems: 'center', padding: '0 12px', marginLeft: 'auto', borderLeft: `1px solid ${t.colors.border}` }}>
                    <span style={{ fontSize: '11px', color: t.colors.textMuted, fontFamily: t.fonts.mono }}>
                        <span style={{ color: t.colors.textPrimary, fontWeight: '600' }}>{pageInfo.current}</span>
                        <span style={{ margin: '0 3px' }}>/</span>
                        {pageInfo.total}
                    </span>
                </div>
            )}
        </div>
    );
};