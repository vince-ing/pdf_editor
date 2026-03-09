// components/StatusBar.jsx
import React from 'react';
import theme from '../theme';
import { TOOL_ICONS } from '../tools';
const t = theme;

export const StatusBar = ({ activeTool, scale, activePage, pageCount, lastSelectedText, documentState }) => (
    <div style={{
        height: t.layout.statusBarH,
        backgroundColor: t.colors.chrome,
        borderTop: `1px solid ${t.colors.border}`,
        display: 'flex', alignItems: 'center', gap: '0',
        padding: '0 12px', flexShrink: 0, overflow: 'hidden',
    }}>
        {[
            { label: TOOL_ICONS[activeTool]?.label, color: t.colors.accent },
            documentState && { label: `${Math.round(scale * 100)}%` },
            documentState && { label: `Page ${activePage + 1} of ${pageCount}` },
        ].filter(Boolean).map((chip, i, arr) => (
            <React.Fragment key={i}>
                <span style={{ fontSize: '10.5px', color: chip.color ?? t.colors.textSecondary, fontFamily: t.fonts.mono, padding: '0 10px', whiteSpace: 'nowrap' }}>
                    {chip.label}
                </span>
                {i < arr.length - 1 && <span style={{ color: t.colors.border, fontSize: '10px' }}>│</span>}
            </React.Fragment>
        ))}

        {lastSelectedText && (
            <span style={{ marginLeft: 'auto', fontSize: '10.5px', color: t.colors.textMuted, fontFamily: t.fonts.ui, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '320px' }}>
                <span style={{ color: t.colors.textMuted }}>Selected: </span>
                <span style={{ color: t.colors.accent }}>
                    {lastSelectedText.length > 60 ? lastSelectedText.slice(0, 60) + '…' : lastSelectedText}
                </span>
            </span>
        )}
    </div>
);